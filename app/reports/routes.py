from flask import Blueprint, render_template, request
from app.auth.routes import login_required, get_current_user
from app.services.attendance_service import get_monthly_stats
from app.services.datetime_service import (
    current_bs_year_month, bs_months_for_select, get_bs_month_range,
    format_bs_date, NEPALI_MONTHS, format_duration
)
from app.models import Attendance

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/reports')
@login_required
def monthly_report():
    user = get_current_user()
    month_param = request.args.get('month', '')
    
    if month_param:
        try:
            y, m = map(int, month_param.split('-'))
        except Exception:
            y, m = current_bs_year_month()
    else:
        y, m = current_bs_year_month()
    
    start_g, end_g = get_bs_month_range(y, m)
    
    # Use Gregorian year/month of the range mid-point for stats helper
    mid = start_g + (end_g - start_g) / 2
    stats = get_monthly_stats(user.id, mid.year, mid.month)
    
    # Override filter to exact BS month range
    records = Attendance.query.filter(
        Attendance.user_id == user.id,
        Attendance.attendance_date >= start_g,
        Attendance.attendance_date <= end_g
    ).order_by(Attendance.attendance_date).all()
    
    completed = [r for r in records if r.is_complete]
    incomplete = [r for r in records if not r.is_complete]
    total_working = sum(r.working_seconds or 0 for r in completed)
    total_overtime = sum(r.overtime_seconds or 0 for r in completed)
    avg_working = total_working // len(completed) if completed else 0
    
    # Chart data
    chart_labels = [format_bs_date(r.attendance_date) for r in records]
    chart_working = [(r.working_seconds or 0) / 3600 for r in records]
    chart_overtime = [(r.overtime_seconds or 0) / 3600 for r in records]
    
    months = bs_months_for_select(18)
    
    return render_template(
        'reports.html',
        user=user,
        records=records,
        months=months,
        selected_month=f'{y}-{m:02d}',
        month_label=f'{NEPALI_MONTHS[m]} {y}',
        present_days=len(records),
        completed_shifts=len(completed),
        incomplete_shifts=len(incomplete),
        total_working_str=format_duration(total_working),
        total_overtime_str=format_duration(total_overtime),
        average_working_str=format_duration(avg_working),
        chart_labels=chart_labels,
        chart_working=chart_working,
        chart_overtime=chart_overtime
    )
