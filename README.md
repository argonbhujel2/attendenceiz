# My Attendance

Personal Attendance Management System for a single user.

Built with Flask, Neon PostgreSQL (or SQLite for local fallback), Bikram Sambat dates, overnight shift support, and PWA.

## Features

- Session-based login (single user)
- Check In / Check Out with Nepal timezone (`Asia/Kathmandu`)
- Overnight shifts (e.g. 19:00 → 07:00 next day)
- Automatic working hours and overtime (standard duty = 12 hours)
- Manual past attendance entry
- Attendance records with month filter and CSV export
- Monthly reports with Chart.js
- All user-facing dates in Bikram Sambat (Devanagari)
- Times in 24-hour format
- Progressive Web App (installable)
- Responsive desktop and mobile UI

## Requirements

- Python 3.10+
- Neon PostgreSQL account (free tier works) **or** SQLite for quick local testing

## Quick Start (Windows)

1. Extract `my-attendance-dashboard.zip`
2. Copy `.env.example` to `.env` and edit values
3. Double-click `run.bat`  
   **or** run in a terminal:

```bat
python -m pip install -r requirements.txt
python wsgi.py
```

If Python is not on PATH, use the full path, for example:

```bat
%USERPROFILE%\Desktop\Python312\python.exe -m pip install -r requirements.txt
%USERPROFILE%\Desktop\Python312\python.exe app.py
```

4. Open http://127.0.0.1:5000

### First-time admin user

Set in `.env`:

```
ADMIN_USERNAME=yourname
ADMIN_PASSWORD=a-strong-password
```

On first launch the app creates this user automatically if no matching user exists.

You can also run:

```
flask --app app.py init-admin
```

## Environment Variables

| Variable         | Description                                      |
|------------------|--------------------------------------------------|
| `SECRET_KEY`     | Long random string for sessions                  |
| `DATABASE_URL`   | Neon connection string (`postgresql://...`)      |
| `ADMIN_USERNAME` | Initial admin username                           |
| `ADMIN_PASSWORD` | Initial admin password                           |
| `FLASK_ENV`      | `development` or `production`                    |

### Neon setup

1. Create a project at [neon.tech](https://neon.tech)
2. Copy the connection string
3. Put it in `.env` as `DATABASE_URL=postgresql://...`

If `DATABASE_URL` is empty, the app falls back to a local SQLite file (`attendance_local.db`) for development only.

## Project Structure

```
attendance-dashboard/
├── app.py                 # Entry point
├── config.py
├── extensions.py
├── requirements.txt
├── .env.example
├── run.bat
├── README.md
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── auth/
│   ├── attendance/
│   ├── reports/
│   ├── services/
│   ├── templates/
│   └── static/
└── tests/
```

## Standard Duty Rules

- Shift start: 19:00
- Expected end: 07:00 next day
- Standard duration: 12 hours
- Overtime = max(working − 12h, 0)

Examples:

| Check In | Check Out | Overnight | Working | Overtime |
|----------|-----------|-----------|---------|----------|
| 19:00    | 07:00     | Yes       | 12:00   | 00:00    |
| 19:00    | 08:30     | Yes       | 13:30   | 01:30    |
| 19:00    | 06:30     | Yes       | 11:30   | 00:00    |
| 19:00    | 23:00     | No        | 04:00   | 00:00    |

## Running Tests

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```

## Deployment (Vercel / Python host)

1. Set environment variables on the host (`SECRET_KEY`, `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `FLASK_ENV=production`)
2. Use a production WSGI server (gunicorn is included)
3. Point the host to `app:app` or the entry file that exposes the Flask app

Example gunicorn:

```bash
gunicorn -w 2 -b 0.0.0.0:8000 "wsgi:app"
```

## PWA / iOS notes

- Android Chrome and desktop Chrome/Edge support install prompts.
- iOS Safari supports “Add to Home Screen” but does not show a custom install banner; users must use the Share sheet.

## Security notes

- Passwords are hashed with Werkzeug (pbkdf2:sha256)
- CSRF protection on forms
- Sessions are HTTP-only; Secure flag enabled in production
- No public registration
- Service worker does **not** cache authenticated pages or attendance data



## Deploy to Vercel

1. Push this project to a GitHub repository.
2. Import the repo in [vercel.com](https://vercel.com).
3. Set **Root Directory** to the project folder if needed.
4. Add Environment Variables in Vercel project settings:

| Name | Value |
|------|-------|
| `SECRET_KEY` | long random string |
| `DATABASE_URL` | your Neon `postgresql://...` connection string |
| `ADMIN_USERNAME` | your login username |
| `ADMIN_PASSWORD` | strong password |
| `FLASK_ENV` | `production` |

5. Deploy. Vercel uses `vercel.json` and the `app` object in `app.py`.

**Important:** Use Neon (or any managed Postgres). SQLite will not work on Vercel because the filesystem is read-only / ephemeral.

After first deploy, open the site and sign in with the admin credentials you set. Tables are created automatically on first request if you hit any route that uses the DB — or call the bootstrap by visiting the login page after setting env vars.

### Neon + Vercel tips

- In Neon, enable the connection string with `?sslmode=require`.
- Prefer the **pooled** connection string for serverless (Vercel).
- Never put secrets in the repo; only in Vercel Environment Variables.

## License

Personal use. Modify as needed for your own attendance tracking.
