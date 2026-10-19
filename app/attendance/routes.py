from flask import Blueprint, render_template, redirect, url_for, flash, request, session, Response
from datetime import date, timedelta
from io import StringIO
import csv

from app.auth.routes import login_required, get_current_user
from app.services.attendance_service import (
    check_in, check_out, create_manual_attendance,
    get_monthly_stats, get_recent_records, get_or_create_today_attendance,
    build_month_day_rows
)
from app.services.datetime_service import (
    today_nepal, now_nepal, format_bs_date, format_time_24,
    parse_time_str, to_bs_date, from_bs_date, current_bs_year_month,
    bs_months_for_select, get_bs_month_range, NEPALI_MONTHS,
    bs_years_for_select, days_in_bs_month, parse_bs_date_parts, to_devanagari
)
from app.models import Attendance
from extensions import db
import nepali_datetime as ndt

attendance_bp = Blueprint('attendance', __name__)


@attendance_bp.route('/')
@login_required
def dashboard():
    user = get_current_user()
    today = today_nepal()
    now = now_nepal()
    
    att = Attendance.query.filter_by(user_id=user.id, attendance_date=today).first()
    
    # Also check if yesterday has incomplete overnight
    yesterday = today - timedelta(days=1)
    yest_att = Attendance.query.filter_by(user_id=user.id, attendance_date=yesterday).first()
    can_checkout_overnight = (
        yest_att and yest_att.check_in and not yest_att.check_out
    )
    
    # Monthly stats (current Gregorian month for simplicity, or BS)
    bs_year, bs_month = current_bs_year_month()
    start_g, end_g = get_bs_month_range(bs_year, bs_month)
    
    month_records = Attendance.query.filter(
        Attendance.user_id == user.id,
        Attendance.attendance_date >= start_g,
        Attendance.attendance_date <= end_g
    ).all()
    
    present_days = len(month_records)
    completed = [r for r in month_records if r.is_complete]
    total_working = sum(r.working_seconds or 0 for r in completed)
    total_overtime = sum(r.overtime_seconds or 0 for r in completed)
    
    from app.services.datetime_service import format_duration
    recent = get_recent_records(user.id, 7)
    
    return render_template(
        'dashboard.html',
        user=user,
        today=today,
        now=now,
        attendance=att,
        can_checkout_overnight=can_checkout_overnight,
        present_days=present_days,
        total_working_str=format_duration(total_working),
        total_overtime_str=format_duration(total_overtime),
        recent=recent,
        bs_month_label=f'{NEPALI_MONTHS[bs_month]} {bs_year}'
    )


@attendance_bp.route('/check-in', methods=['POST'])
@login_required
def do_check_in():
    user = get_current_user()
    success, message, _ = check_in(user.id)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('attendance.dashboard'))


@attendance_bp.route('/check-out', methods=['POST'])
@login_required
def do_check_out():
    user = get_current_user()
    success, message, _ = check_out(user.id)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('attendance.dashboard'))


@attendance_bp.route('/records')
@login_required
def records():
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    month_filter = request.args.get('month', '')

    months = bs_months_for_select(18)
    day_rows = None
    records_list = None

    query = Attendance.query.filter_by(user_id=user.id)

    if month_filter:
        try:
            y, m = map(int, month_filter.split('-'))
            start_g, end_g = get_bs_month_range(y, m)
            query = query.filter(
                Attendance.attendance_date >= start_g,
                Attendance.attendance_date <= end_g
            )
            # Full calendar rows including Absent for missing past days
            day_rows = build_month_day_rows(user.id, start_g, end_g)
        except Exception:
            day_rows = None

    if day_rows is None:
        records_list = query.order_by(Attendance.attendance_date.desc()).paginate(
            page=page, per_page=20, error_out=False
        )

    all_filtered = query.all()
    completed = [r for r in all_filtered if r.is_complete]
    from app.services.datetime_service import format_duration
    total_w = sum(r.working_seconds or 0 for r in completed)
    total_o = sum(r.overtime_seconds or 0 for r in completed)

    # Status counts
    absent_count = 0
    if day_rows is not None:
        absent_count = sum(1 for row in day_rows if row['is_absent'])
    else:
        absent_count = sum(1 for r in all_filtered if r.status == 'absent')

    overtime_count = sum(1 for r in all_filtered if r.status == 'overtime')
    late_count = sum(1 for r in all_filtered if r.status == 'late')
    complete_count = sum(1 for r in all_filtered if r.status == 'complete')

    return render_template(
        'records.html',
        user=user,
        records=records_list,
        day_rows=day_rows,
        months=months,
        selected_month=month_filter,
        present_days=len(all_filtered),
        total_working_str=format_duration(total_w),
        total_overtime_str=format_duration(total_o),
        absent_count=absent_count,
        overtime_count=overtime_count,
        late_count=late_count,
        complete_count=complete_count
    )


@attendance_bp.route('/manual', methods=['GET', 'POST'])
@login_required
def manual_entry():
    user = get_current_user()
    today_bs = to_bs_date(today_nepal())
    years = bs_years_for_select(6)
    months_list = [{'num': i, 'name': NEPALI_MONTHS[i]} for i in range(1, 13)]

    def form_ctx(**extra):
        ctx = dict(
            user=user,
            years=years,
            months_list=months_list,
            selected_year=extra.get('selected_year', today_bs.year),
            selected_month=extra.get('selected_month', today_bs.month),
            selected_day=extra.get('selected_day', 1),
            today_bs=today_bs,
        )
        ctx.update(extra)
        return ctx

    if request.method == 'POST':
        # Collect all row indices from form keys like bs_year_0, bs_year_1, ...
        indices = set()
        for key in request.form:
            if key.startswith('bs_year_'):
                try:
                    indices.add(int(key.split('_')[-1]))
                except ValueError:
                    pass
        indices = sorted(indices)
        if not indices:
            flash('No entries submitted.', 'error')
            return render_template('manual_entry.html', **form_ctx())

        ok_count = 0
        errors = []
        for i in indices:
            try:
                bs_year = int(request.form.get(f'bs_year_{i}', 0))
                bs_month = int(request.form.get(f'bs_month_{i}', 0))
                bs_day = int(request.form.get(f'bs_day_{i}', 0))
                att_date = parse_bs_date_parts(bs_year, bs_month, bs_day)
            except (ValueError, TypeError) as e:
                errors.append(f'Entry #{i + 1}: invalid B.S. date')
                continue

            check_in_str = request.form.get(f'check_in_{i}', '')
            check_out_str = request.form.get(f'check_out_{i}', '')
            next_day = request.form.get(f'checkout_next_day_{i}') == 'on'
            notes = request.form.get(f'notes_{i}', '')

            try:
                ci_time = parse_time_str(check_in_str)
                co_time = parse_time_str(check_out_str)
            except ValueError as e:
                errors.append(f'Entry #{i + 1}: {e}')
                continue

            success, message, att = create_manual_attendance(
                user.id, att_date, ci_time, co_time, next_day, notes
            )
            if success:
                ok_count += 1
            else:
                errors.append(f'Entry #{i + 1}: {message}')

        if ok_count:
            flash(f'{ok_count} attendance record(s) saved.', 'success')
        for err in errors:
            flash(err, 'error')

        if ok_count and not errors:
            return redirect(url_for('attendance.records'))
        if ok_count:
            return redirect(url_for('attendance.records'))
        yest = today_nepal() - timedelta(days=1)
        yest_bs = to_bs_date(yest)
        return render_template(
            'manual_entry.html',
            **form_ctx(
                selected_year=yest_bs.year,
                selected_month=yest_bs.month,
                selected_day=yest_bs.day,
            )
        )

    yest = today_nepal() - timedelta(days=1)
    yest_bs = to_bs_date(yest)
    return render_template(
        'manual_entry.html',
        **form_ctx(
            selected_year=yest_bs.year,
            selected_month=yest_bs.month,
            selected_day=yest_bs.day,
        )
    )




@attendance_bp.route('/api/bs-days')
@login_required
def api_bs_days():
    """Return number of days in a B.S. year-month as JSON."""
    from flask import jsonify
    try:
        y = int(request.args.get('year', 0))
        m = int(request.args.get('month', 0))
        if not (1 <= m <= 12) or y < 1970:
            return jsonify({'days': 30, 'error': 'invalid'}), 400
        days = days_in_bs_month(y, m)
        return jsonify({'year': y, 'month': m, 'days': days})
    except Exception as e:
        return jsonify({'days': 30, 'error': str(e)}), 400

@attendance_bp.route('/export/csv')
@login_required
def export_csv():
    user = get_current_user()
    month_filter = request.args.get('month', '')
    
    query = Attendance.query.filter_by(user_id=user.id)
    if month_filter:
        try:
            y, m = map(int, month_filter.split('-'))
            start_g, end_g = get_bs_month_range(y, m)
            query = query.filter(
                Attendance.attendance_date >= start_g,
                Attendance.attendance_date <= end_g
            )
        except Exception:
            pass
    
    records_list = query.order_by(Attendance.attendance_date.desc()).all()
    
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow([
        'BS Date', 'Check In', 'Check Out', 'Next Day',
        'Working Duration', 'Overtime', 'Notes'
    ])
    
    for r in records_list:
        writer.writerow([
            format_bs_date(r.attendance_date),
            format_time_24(r.check_in),
            format_time_24(r.check_out),
            'Yes' if r.checkout_next_day else 'No',
            r.working_duration_str,
            r.overtime_duration_str,
            r.notes or ''
        ])
    
    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=attendance_export.csv'}
    )


@attendance_bp.route('/offline')
def offline_page():
    """Offline fallback page (no auth required)."""
    return render_template('offline.html')
