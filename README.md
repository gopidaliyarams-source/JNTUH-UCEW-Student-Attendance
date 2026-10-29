# JNTUH UCEW Wanaparthy — Student Attendance Management System

A full-stack **starter prototype** for a college attendance workflow:
- Admin: manage demo student accounts, faculty accounts, and subject/class assignments.
- Faculty: mark and update student attendance for assigned subjects.
- Student: view their own attendance percentage and subject-wise history.
- Reports: export saved attendance as CSV (opens in Excel).

## Run on macOS

1. Install Python 3 if it is not installed.
2. Extract this ZIP and open Terminal in the extracted folder.
3. Create a virtual environment and install requirements:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```

4. Open `http://127.0.0.1:5000` in your browser.

## Demo accounts

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `Admin@123` |
| Faculty | `faculty1` | `Faculty@123` |
| Student | `26xw5a0501` | `Student@123` |

The app creates `attendance.db` on the first run and seeds fictional sample data. The sample student accounts are fictional test data and should be replaced with authorized college records.

## Important before real deployment

This is a learning/demo prototype, **not an official JNTUH service**. It has not been security-audited. Before use with real students:
- Set a strong random `SECRET_KEY` environment variable.
- Disable Flask debug mode and run behind a production WSGI server over HTTPS.
- Add CSRF protection, rate limiting, password reset/rotation, secure cookie settings, audit logs, backups, and account lifecycle controls.
- Add the college's approved policies for attendance correction, access retention, and report access.
- Import only authorized student/faculty data and test access control thoroughly.
- Confirm the institution's permission to use its name/logo. This starter uses a text-based JNTUH label and is not endorsed by the university.

## Notes

- Attendance is stored in a local SQLite database on the computer running the app; it is not yet hosted online or shared across devices.
- Faculty can only mark attendance for their assigned subjects.
- Student attendance percentage is calculated from recorded attendance entries; it is not a substitute for official academic records.
- CSV export is provided and can be opened with Microsoft Excel.
