"""Nepal timezone and Bikram Sambat date utilities.

IMPORTANT: Attendance check_in / check_out are stored as *naive* datetimes
representing Asia/Kathmandu wall-clock time (no UTC conversion).
This avoids the classic 19:00 → 13:15 shift when using Postgres timestamptz.
"""
from datetime import datetime, date, time, timedelta
import pytz
import nepali_datetime as ndt

NEPAL_TZ = pytz.timezone('Asia/Kathmandu')

NEPALI_MONTHS = [
    '', 'बैशाख', 'जेठ', 'असार', 'साउन', 'भदौ', 'असोज',
    'कात्तिक', 'मंसिर', 'पुष', 'माघ', 'फागुन', 'चैत'
]

DEVANAGARI_DIGITS = str.maketrans('0123456789', '०१२३४५६७८९')


def now_nepal() -> datetime:
    """Current Nepal local time as *naive* datetime (wall clock)."""
    return datetime.now(NEPAL_TZ).replace(tzinfo=None)


def now_nepal_aware() -> datetime:
    """Current Nepal local time as timezone-aware datetime."""
    return datetime.now(NEPAL_TZ)


def today_nepal() -> date:
    """Today's date in Nepal timezone."""
    return datetime.now(NEPAL_TZ).date()


def to_nepal_naive(dt: datetime | None) -> datetime | None:
    """
    Normalize any datetime to naive Nepal wall-clock time for display/storage.
    - If aware: convert to Asia/Kathmandu then strip tzinfo
    - If naive: assume already Nepal local, return as-is
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(NEPAL_TZ).replace(tzinfo=None)
    return dt.replace(tzinfo=None)


def make_nepal_datetime(d: date, t: time) -> datetime:
    """Combine date + time into naive Nepal wall-clock datetime (as entered by user)."""
    return datetime.combine(d, t)


def format_time_24(dt: datetime | None) -> str:
    """Format as HH:MM in Nepal local time (24-hour)."""
    if dt is None:
        return '—'
    local = to_nepal_naive(dt)
    return local.strftime('%H:%M')


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return '—'
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f'{hours:02d}:{minutes:02d}'


def to_bs_date(d: date) -> ndt.date:
    return ndt.date.from_datetime_date(d)


def from_bs_date(bs: ndt.date) -> date:
    return bs.to_datetime_date()


def format_bs_date(d: date | None, with_day: bool = False) -> str:
    if d is None:
        return '—'
    bs = to_bs_date(d)
    day = str(bs.day).translate(DEVANAGARI_DIGITS)
    month = NEPALI_MONTHS[bs.month]
    year = str(bs.year).translate(DEVANAGARI_DIGITS)
    return f'{day} {month} {year}'


def format_bs_datetime(dt: datetime | None) -> str:
    if dt is None:
        return '—'
    local = to_nepal_naive(dt)
    return f'{format_bs_date(local.date())} {format_time_24(local)}'


def parse_time_str(time_str: str) -> time:
    parts = time_str.strip().split(':')
    if len(parts) != 2:
        raise ValueError('Time must be in HH:MM format')
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError('Invalid time values')
    return time(hour, minute)


def get_bs_month_range(year_bs: int, month_bs: int) -> tuple[date, date]:
    start_bs = ndt.date(year_bs, month_bs, 1)
    if month_bs == 12:
        next_bs = ndt.date(year_bs + 1, 1, 1)
    else:
        next_bs = ndt.date(year_bs, month_bs + 1, 1)
    end_bs = next_bs - timedelta(days=1)
    return start_bs.to_datetime_date(), end_bs.to_datetime_date()


def current_bs_year_month() -> tuple[int, int]:
    bs = to_bs_date(today_nepal())
    return bs.year, bs.month


def bs_months_for_select(count: int = 12) -> list[dict]:
    today_bs = to_bs_date(today_nepal())
    months = []
    y, m = today_bs.year, today_bs.month
    for i in range(count):
        months.append({
            'year': y,
            'month': m,
            'label': f'{NEPALI_MONTHS[m]} {str(y).translate(DEVANAGARI_DIGITS)}',
            'value': f'{y}-{m:02d}'
        })
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    return months


def bs_years_for_select(count: int = 5) -> list[int]:
    today_bs = to_bs_date(today_nepal())
    return list(range(today_bs.year, today_bs.year - count, -1))


def days_in_bs_month(year_bs: int, month_bs: int) -> int:
    try:
        start = ndt.date(int(year_bs), int(month_bs), 1)
        if int(month_bs) == 12:
            nxt = ndt.date(int(year_bs) + 1, 1, 1)
        else:
            nxt = ndt.date(int(year_bs), int(month_bs) + 1, 1)
        return (nxt - start).days
    except Exception:
        for d in range(32, 27, -1):
            try:
                ndt.date(int(year_bs), int(month_bs), d)
                return d
            except Exception:
                continue
        return 30


def parse_bs_date_parts(year: int, month: int, day: int) -> date:
    year, month, day = int(year), int(month), int(day)
    max_day = days_in_bs_month(year, month)
    month_name = NEPALI_MONTHS[month] if 1 <= month <= 12 else str(month)
    if day < 1 or day > max_day:
        raise ValueError(
            f'{month_name} {year} मा {max_day} दिन मात्र छ। '
            f'गते {day} मान्य छैन (अन्तिम गते: {max_day})।'
        )
    try:
        bs = ndt.date(year, month, day)
        return bs.to_datetime_date()
    except Exception as e:
        raise ValueError(
            f'अमान्य B.S. मिति: {day} {month_name} {year}. '
            f'त्यो महिनामा {max_day} दिन छन्।'
        ) from e


def to_devanagari(n: int | str) -> str:
    return str(n).translate(DEVANAGARI_DIGITS)
