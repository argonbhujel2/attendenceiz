"""Unit tests for overtime and duration calculations."""
import pytest
from datetime import datetime, date, time, timedelta
from app.services.datetime_service import make_nepal_datetime, NEPAL_TZ
from app.models import Attendance


def make_att(check_in_h, check_in_m, check_out_h, check_out_m, next_day=False, base_date=None):
    if base_date is None:
        base_date = date(2025, 1, 15)
    ci = make_nepal_datetime(base_date, time(check_in_h, check_in_m))
    if next_day:
        co = make_nepal_datetime(base_date + timedelta(days=1), time(check_out_h, check_out_m))
    else:
        co = make_nepal_datetime(base_date, time(check_out_h, check_out_m))
    att = Attendance(
        user_id=1,
        attendance_date=base_date,
        check_in=ci,
        check_out=co,
        checkout_next_day=next_day
    )
    att.calculate_durations()
    return att


def test_standard_12h_overnight():
    """19:00 -> 07:00 next day = 12:00 working, 0 OT"""
    att = make_att(19, 0, 7, 0, next_day=True)
    assert att.working_seconds == 12 * 3600
    assert att.overtime_seconds == 0
    assert att.working_duration_str == '12:00'
    assert att.overtime_duration_str == '00:00'


def test_overtime_13h30():
    """19:00 -> 08:30 next day = 13:30 working, 1:30 OT"""
    att = make_att(19, 0, 8, 30, next_day=True)
    assert att.working_seconds == 13 * 3600 + 30 * 60
    assert att.overtime_seconds == 1 * 3600 + 30 * 60
    assert att.working_duration_str == '13:30'
    assert att.overtime_duration_str == '01:30'


def test_under_12h():
    """19:00 -> 06:30 next day = 11:30 working, 0 OT"""
    att = make_att(19, 0, 6, 30, next_day=True)
    assert att.working_seconds == 11 * 3600 + 30 * 60
    assert att.overtime_seconds == 0


def test_same_day_short():
    """19:00 -> 23:00 same day = 4:00 working, 0 OT"""
    att = make_att(19, 0, 23, 0, next_day=False)
    assert att.working_seconds == 4 * 3600
    assert att.overtime_seconds == 0


def test_reject_over_24h():
    att = Attendance(
        user_id=1,
        attendance_date=date(2025, 1, 15),
        check_in=make_nepal_datetime(date(2025, 1, 15), time(8, 0)),
        check_out=make_nepal_datetime(date(2025, 1, 16), time(10, 0)),
        checkout_next_day=True
    )
    with pytest.raises(ValueError):
        att.calculate_durations()
