from datetime import datetime, date, time, timedelta
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
import pytz

NEPAL_TZ = pytz.timezone('Asia/Kathmandu')

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(NEPAL_TZ).replace(tzinfo=None))
    
    attendances = db.relationship('Attendance', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Attendance(db.Model):
    __tablename__ = 'attendances'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    check_in = db.Column(db.DateTime, nullable=True)  # Stored as naive UTC-aware converted
    check_out = db.Column(db.DateTime, nullable=True)
    checkout_next_day = db.Column(db.Boolean, default=False)
    working_seconds = db.Column(db.Integer, nullable=True)
    overtime_seconds = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(NEPAL_TZ).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(NEPAL_TZ).replace(tzinfo=None), onupdate=lambda: datetime.now(NEPAL_TZ).replace(tzinfo=None))
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'attendance_date', name='uq_user_attendance_date'),
    )
    
    def calculate_durations(self):
        """Calculate working and overtime seconds from check_in and check_out."""
        if not self.check_in or not self.check_out:
            self.working_seconds = None
            self.overtime_seconds = None
            return

        # Normalize to naive Nepal wall-clock before subtracting
        def _naive(dt):
            if dt.tzinfo is not None:
                return dt.astimezone(NEPAL_TZ).replace(tzinfo=None)
            return dt.replace(tzinfo=None)

        ci = _naive(self.check_in)
        co = _naive(self.check_out)
        delta = co - ci
        total_seconds = int(delta.total_seconds())
        
        if total_seconds < 0 or total_seconds > 24 * 3600:
            raise ValueError("Invalid duration: must be between 0 and 24 hours")
        
        self.working_seconds = total_seconds
        standard_seconds = 12 * 3600  # 12 hours
        self.overtime_seconds = max(total_seconds - standard_seconds, 0)
    
    @property
    def working_duration_str(self):
        if self.working_seconds is None:
            return '—'
        hours = self.working_seconds // 3600
        minutes = (self.working_seconds % 3600) // 60
        return f'{hours:02d}:{minutes:02d}'
    
    @property
    def overtime_duration_str(self):
        if self.overtime_seconds is None:
            return '—'
        hours = self.overtime_seconds // 3600
        minutes = (self.overtime_seconds % 3600) // 60
        return f'{hours:02d}:{minutes:02d}'
    
    @property
    def is_complete(self):
        return self.check_in is not None and self.check_out is not None

    # Expected shift start: 19:00 Nepal time
    EXPECTED_START_HOUR = 19
    EXPECTED_START_MINUTE = 0
    STANDARD_SECONDS = 12 * 3600
    TOLERANCE_SECONDS = 10 * 60  # ±10 minutes for "Complete"

    @property
    def status(self) -> str:
        """
        Status labels:
        - absent: no check-in (and no check-out)
        - incomplete: checked in but not out
        - late: check-in after expected start (19:00), completed shift
        - overtime: has overtime (>12h)
        - complete: working duration within ±10 min of 12h
        - short: completed but under 12h-10min (and not late-focused)
        """
        if not self.check_in and not self.check_out:
            return 'absent'
        if self.check_in and not self.check_out:
            return 'incomplete'

        # Completed shift
        is_late = self._is_late_checkin()
        has_ot = (self.overtime_seconds or 0) > 0
        ws = self.working_seconds or 0
        low = self.STANDARD_SECONDS - self.TOLERANCE_SECONDS
        high = self.STANDARD_SECONDS + self.TOLERANCE_SECONDS

        if has_ot:
            return 'overtime'
        if is_late:
            return 'late'
        if low <= ws <= high:
            return 'complete'
        if ws < low:
            return 'short'
        # slightly over tolerance but no formal OT bucket — treat as overtime edge
        return 'overtime'

    def _is_late_checkin(self) -> bool:
        if not self.check_in:
            return False
        from datetime import datetime as dt
        # Normalize both sides to naive local wall-clock in Nepal
        ci = self.check_in
        if ci.tzinfo is not None:
            ci = ci.astimezone(NEPAL_TZ).replace(tzinfo=None)
        else:
            ci = ci.replace(tzinfo=None)
        expected = dt.combine(
            self.attendance_date,
            time(self.EXPECTED_START_HOUR, self.EXPECTED_START_MINUTE)
        )
        return ci > expected

    @property
    def status_label(self) -> str:
        return {
            'absent': 'Absent',
            'incomplete': 'Incomplete',
            'late': 'Late',
            'overtime': 'Overtime',
            'complete': 'Complete',
            'short': 'Short',
        }.get(self.status, self.status.title())

    @property
    def status_badge_class(self) -> str:
        return {
            'absent': 'badge-absent',
            'incomplete': 'badge-warning',
            'late': 'badge-late',
            'overtime': 'badge-overtime',
            'complete': 'badge-success',
            'short': 'badge-short',
        }.get(self.status, 'badge-muted')
    
    def __repr__(self):
        return f'<Attendance {self.attendance_date} user={self.user_id}>'



class AppMeta(db.Model):
    """Key-value store for one-time migrations / app flags."""
    __tablename__ = 'app_meta'

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(256), nullable=True)
