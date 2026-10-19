"""Attendance business logic and calculations."""
from datetime import datetime, date, time, timedelta
from typing import Optional, Tuple
from sqlalchemy.exc import IntegrityError

from extensions import db
from app.models import Attendance, User
from app.services.datetime_service import (
    now_nepal, today_nepal, make_nepal_datetime, NEPAL_TZ,
    format_duration, parse_time_str
)

STANDARD_SECONDS = 12 * 3600  # 12 hours


def get_or_create_today_attendance(user_id: int) -> Attendance:
    """Get today's attendance record or create a new empty one."""
    today = today_nepal()
    att = Attendance.query.filter_by(user_id=user_id, attendance_date=today).first()
    if not att:
        att = Attendance(user_id=user_id, attendance_date=today)
        db.session.add(att)
        db.session.commit()
    return att


def check_in(user_id: int) -> Tuple[bool, str, Optional[Attendance]]:
    """
    Perform check-in for today.
    Returns (success, message, attendance).
    """
    today = today_nepal()
    existing = Attendance.query.filter_by(user_id=user_id, attendance_date=today).first()
    
    if existing and existing.check_in is not None:
        return False, 'You have already checked in for today.', existing
    
    now = now_nepal()
    
    if existing:
        existing.check_in = now
        existing.updated_at = now
        att = existing
    else:
        att = Attendance(
            user_id=user_id,
            attendance_date=today,
            check_in=now
        )
        db.session.add(att)
    
    try:
        db.session.commit()
        return True, f'Checked in at {now.strftime("%H:%M")}.', att
    except Exception as e:
        db.session.rollback()
        return False, 'Failed to record check-in. Please try again.', None


def check_out(user_id: int) -> Tuple[bool, str, Optional[Attendance]]:
    """
    Perform check-out for today's attendance (handles overnight).
    Returns (success, message, attendance).
    """
    today = today_nepal()
    now = now_nepal()
    
    # First look for today's record with check-in but no check-out
    att = Attendance.query.filter_by(
        user_id=user_id,
        attendance_date=today
    ).first()
    
    if att and att.check_in and not att.check_out:
        # Same-day or overnight checkout for today's shift
        att.check_out = now
        # Determine if next day
        if now.date() > att.attendance_date:
            att.checkout_next_day = True
        try:
            att.calculate_durations()
        except ValueError as e:
            return False, str(e), att
        att.updated_at = now
        try:
            db.session.commit()
            return True, (
                f'Checked out at {now.strftime("%H:%M")}. '
                f'Working: {att.working_duration_str}, Overtime: {att.overtime_duration_str}.'
            ), att
        except Exception:
            db.session.rollback()
            return False, 'Failed to record check-out. Please try again.', None
    
    # Check for yesterday's incomplete overnight shift
    yesterday = today - timedelta(days=1)
    att_y = Attendance.query.filter_by(
        user_id=user_id,
        attendance_date=yesterday
    ).first()
    
    if att_y and att_y.check_in and not att_y.check_out:
        att_y.check_out = now
        att_y.checkout_next_day = True
        try:
            att_y.calculate_durations()
        except ValueError as e:
            return False, str(e), att_y
        att_y.updated_at = now
        try:
            db.session.commit()
            return True, (
                f'Checked out at {now.strftime("%H:%M")} (overnight). '
                f'Working: {att_y.working_duration_str}, Overtime: {att_y.overtime_duration_str}.'
            ), att_y
        except Exception:
            db.session.rollback()
            return False, 'Failed to record check-out. Please try again.', None
    
    if att and att.check_out:
        return False, 'You have already checked out for today.', att
    
    return False, 'No active check-in found. Please check in first.', None


def create_manual_attendance(
    user_id: int,
    attendance_date: date,
    check_in_time: time,
    check_out_time: time,
    checkout_next_day: bool = False,
    notes: str = None
) -> Tuple[bool, str, Optional[Attendance]]:
    """
    Create a past attendance record manually.
    Only allows dates strictly before today.
    """
    today = today_nepal()
    if attendance_date >= today:
        return False, 'Manual entry is only allowed for past dates.', None
    
    existing = Attendance.query.filter_by(
        user_id=user_id,
        attendance_date=attendance_date
    ).first()
    if existing:
        return False, 'An attendance record already exists for this date.', None
    
    check_in_dt = make_nepal_datetime(attendance_date, check_in_time)
    
    if checkout_next_day:
        check_out_dt = make_nepal_datetime(attendance_date + timedelta(days=1), check_out_time)
    else:
        check_out_dt = make_nepal_datetime(attendance_date, check_out_time)
    
    if check_out_dt <= check_in_dt:
        return False, 'Check-out must be after check-in.', None
    
    delta = check_out_dt - check_in_dt
    total_seconds = int(delta.total_seconds())
    if total_seconds > 24 * 3600:
        return False, 'Working duration cannot exceed 24 hours.', None
    
    att = Attendance(
        user_id=user_id,
        attendance_date=attendance_date,
        check_in=check_in_dt,
        check_out=check_out_dt,
        checkout_next_day=checkout_next_day,
        notes=notes.strip() if notes else None
    )
    att.calculate_durations()
    
    try:
        db.session.add(att)
        db.session.commit()
        return True, (
            f'Record saved. Working: {att.working_duration_str}, '
            f'Overtime: {att.overtime_duration_str}.'
        ), att
    except IntegrityError:
        db.session.rollback()
        return False, 'An attendance record already exists for this date.', None
    except Exception as e:
        db.session.rollback()
        return False, f'Failed to save record: {str(e)}', None


def get_monthly_stats(user_id: int, year: int, month: int) -> dict:
    """
    Compute monthly statistics from actual records.
    year/month are Gregorian for filtering (caller converts from BS).
    """
    from calendar import monthrange
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    
    records = Attendance.query.filter(
        Attendance.user_id == user_id,
        Attendance.attendance_date >= start,
        Attendance.attendance_date <= end
    ).order_by(Attendance.attendance_date).all()
    
    present_days = len(records)
    completed = [r for r in records if r.is_complete]
    incomplete = [r for r in records if not r.is_complete]
    
    total_working = sum(r.working_seconds or 0 for r in completed)
    total_overtime = sum(r.overtime_seconds or 0 for r in completed)
    
    avg_working = total_working // len(completed) if completed else 0
    
    daily_working = []
    daily_overtime = []
    for r in records:
        daily_working.append({
            'date': r.attendance_date,
            'seconds': r.working_seconds or 0,
            'label': format_duration(r.working_seconds)
        })
        daily_overtime.append({
            'date': r.attendance_date,
            'seconds': r.overtime_seconds or 0,
            'label': format_duration(r.overtime_seconds)
        })
    
    return {
        'present_days': present_days,
        'completed_shifts': len(completed),
        'incomplete_shifts': len(incomplete),
        'total_working_seconds': total_working,
        'total_overtime_seconds': total_overtime,
        'total_working_str': format_duration(total_working),
        'total_overtime_str': format_duration(total_overtime),
        'average_working_str': format_duration(avg_working),
        'records': records,
        'daily_working': daily_working,
        'daily_overtime': daily_overtime
    }


def get_recent_records(user_id: int, limit: int = 10):
    return Attendance.query.filter_by(user_id=user_id)\
        .order_by(Attendance.attendance_date.desc())\
        .limit(limit).all()


def build_month_day_rows(user_id: int, start_g: date, end_g: date, today: date | None = None):
    """
    Build one row per calendar day in [start_g, end_g].
    Past days without a record appear as synthetic Absent rows.
    Future days are skipped. Today without record is shown as not-yet (not absent).
    """
    from app.services.datetime_service import today_nepal
    if today is None:
        today = today_nepal()

    records = Attendance.query.filter(
        Attendance.user_id == user_id,
        Attendance.attendance_date >= start_g,
        Attendance.attendance_date <= end_g
    ).all()
    by_date = {r.attendance_date: r for r in records}

    rows = []
    d = start_g
    while d <= end_g:
        if d > today:
            d += timedelta(days=1)
            continue
        att = by_date.get(d)
        if att:
            rows.append({'date': d, 'attendance': att, 'is_absent': att.status == 'absent'})
        else:
            # No record — absent only for past days; today stays empty/not started
            if d < today:
                rows.append({'date': d, 'attendance': None, 'is_absent': True})
            else:
                rows.append({'date': d, 'attendance': None, 'is_absent': False})
        d += timedelta(days=1)

    # Newest first
    rows.reverse()
    return rows


def fix_legacy_utc_shifted_times() -> int:
    """
    One-time fix: older versions stored Nepal times as timestamptz,
    so 19:00 NPT was saved/shown as 13:15 (UTC).

    Adds +5 hours 45 minutes to every check_in and check_out, then
    recalculates working/overtime seconds.

    Safe to call multiple times only when gated by AppMeta flag.
    Returns number of records updated.
    """
    from datetime import timedelta
    NEPAL_OFFSET = timedelta(hours=5, minutes=45)

    records = Attendance.query.all()
    updated = 0
    for att in records:
        changed = False
        if att.check_in is not None:
            ci = att.check_in
            if ci.tzinfo is not None:
                ci = ci.replace(tzinfo=None)
            att.check_in = ci + NEPAL_OFFSET
            changed = True
        if att.check_out is not None:
            co = att.check_out
            if co.tzinfo is not None:
                co = co.replace(tzinfo=None)
            att.check_out = co + NEPAL_OFFSET
            changed = True
        if changed and att.check_in and att.check_out:
            try:
                att.calculate_durations()
            except ValueError:
                pass
        if changed:
            updated += 1
    if updated:
        db.session.commit()
    return updated
