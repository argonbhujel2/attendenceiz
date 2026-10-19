"""
My Attendance — Personal Attendance Management System

Local:
    python wsgi.py

Vercel uses this file as the WSGI entry (module exposes `app`).
Do NOT name this file app.py (conflicts with the app/ package).
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, '.env'))

from app import create_app
from extensions import db

app = create_app()


def init_database():
    """Create tables, bootstrap admin, fix legacy timezone-shifted times once."""
    with app.app_context():
        from app.models import User, Attendance, AppMeta  # noqa: F401
        db.create_all()
        print('Database tables ready.')

        # One-time fix: 19:00 was stored/shown as 13:15 (UTC shift)
        FLAG = 'legacy_utc_times_fixed_v1'
        flag = db.session.get(AppMeta, FLAG)
        if flag is None:
            try:
                from app.services.attendance_service import fix_legacy_utc_shifted_times
                n = fix_legacy_utc_shifted_times()
                db.session.add(AppMeta(key=FLAG, value=f'updated:{n}'))
                db.session.commit()
                print(f'Legacy timezone fix applied to {n} attendance record(s).')
            except Exception as e:
                db.session.rollback()
                print(f'Legacy timezone fix skipped: {e}')
        else:
            print(f'Legacy timezone fix already applied ({flag.value}).')

        admin_user = (os.environ.get('ADMIN_USERNAME') or '').strip()
        admin_pass = (os.environ.get('ADMIN_PASSWORD') or '').strip()

        if not admin_user or not admin_pass:
            print('WARNING: ADMIN_USERNAME / ADMIN_PASSWORD not set.')
            return

        existing = User.query.filter_by(username=admin_user).first()
        if existing:
            print(f'Admin user "{admin_user}" already exists.')
        else:
            user = User(username=admin_user)
            user.set_password(admin_pass)
            db.session.add(user)
            db.session.commit()
            print(f'Created admin user: {admin_user}')


# Always try init on import (Vercel cold start + local)
try:
    init_database()
except Exception as e:
    print(f'DB init skipped/failed: {e}')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    print(f'Starting My Attendance on http://127.0.0.1:{port}')
    print('Press Ctrl+C to stop.')
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)
