import os, csv, io, sqlite3
from datetime import date
from functools import wraps

import psycopg
from psycopg.rows import dict_row
from flask import Flask, request, jsonify, send_from_directory, session, Response
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
USE_POSTGRES = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgresql+")
DB = os.path.join(BASE, "attendance.db")
app = Flask(__name__, static_folder="static")
SECRET_KEY = os.environ.get("SECRET_KEY")
if USE_POSTGRES and not SECRET_KEY:
    raise RuntimeError("Set a strong SECRET_KEY environment variable before running with PostgreSQL.")
app.secret_key = SECRET_KEY or "local-development-only-change-before-deployment"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
)
BRANCHES = ["CSE", "CSE (AI & ML)", "ECE", "Civil", "Mechanical"]

class ConnectionAdapter:
    """Small compatibility wrapper so the same routes can use SQLite locally and PostgreSQL on Render."""
    def __init__(self):
        self.is_postgres = USE_POSTGRES
        if self.is_postgres:
            self.raw = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
        else:
            self.raw = sqlite3.connect(DB)
            self.raw.row_factory = sqlite3.Row
            self.raw.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql, params=()):
        if self.is_postgres:
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, params)

    def commit(self):
        return self.raw.commit()

    def rollback(self):
        return self.raw.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            self.raw.close()
        return False

def connect():
    return ConnectionAdapter()

INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)

def init_db():
    if USE_POSTGRES:
        schema = [
            """CREATE TABLE IF NOT EXISTS users(
              id BIGSERIAL PRIMARY KEY,
              username TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              full_name TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('admin','faculty','student')),
              roll_no TEXT UNIQUE,
              branch TEXT,
              year TEXT,
              section TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS subjects(
              id BIGSERIAL PRIMARY KEY,
              code TEXT NOT NULL,
              name TEXT NOT NULL,
              branch TEXT NOT NULL,
              year TEXT NOT NULL,
              section TEXT NOT NULL,
              faculty_id BIGINT REFERENCES users(id)
            )""",
            """CREATE TABLE IF NOT EXISTS attendance(
              id BIGSERIAL PRIMARY KEY,
              student_id BIGINT NOT NULL REFERENCES users(id),
              subject_id BIGINT NOT NULL REFERENCES subjects(id),
              attendance_date TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('Present','Absent')),
              marked_by BIGINT NOT NULL REFERENCES users(id),
              UNIQUE(student_id, subject_id, attendance_date)
            )""",
        ]
    else:
        schema = [
            """CREATE TABLE IF NOT EXISTS users(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              full_name TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('admin','faculty','student')),
              roll_no TEXT UNIQUE,
              branch TEXT,
              year TEXT,
              section TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS subjects(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              code TEXT NOT NULL,
              name TEXT NOT NULL,
              branch TEXT NOT NULL,
              year TEXT NOT NULL,
              section TEXT NOT NULL,
              faculty_id INTEGER REFERENCES users(id)
            )""",
            """CREATE TABLE IF NOT EXISTS attendance(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              student_id INTEGER NOT NULL REFERENCES users(id),
              subject_id INTEGER NOT NULL REFERENCES subjects(id),
              attendance_date TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('Present','Absent')),
              marked_by INTEGER NOT NULL REFERENCES users(id),
              UNIQUE(student_id, subject_id, attendance_date)
            )""",
        ]
    with connect() as con:
        for statement in schema:
            con.execute(statement)
        count = con.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        if count == 0 and USE_POSTGRES:
            # Production database: create only the initial administrator from Render environment variables.
            admin_username = os.environ.get("INITIAL_ADMIN_USERNAME", "admin").strip().lower()
            admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
            admin_name = os.environ.get("INITIAL_ADMIN_NAME", "College Administrator").strip()
            if len(admin_password) < 12:
                raise RuntimeError(
                    "For a new PostgreSQL database, set INITIAL_ADMIN_PASSWORD to a strong password of at least 12 characters."
                )
            con.execute(
                "INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)",
                (admin_username, generate_password_hash(admin_password), admin_name, "admin"),
            )
        elif count == 0:
            # Local SQLite development only: seed sample data for easy testing.
            con.execute(
                "INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)",
                ("admin", generate_password_hash("Admin@123"), "College Administrator", "admin"),
            )
            faculty_id = con.execute(
                "INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?) RETURNING id",
                ("faculty1", generate_password_hash("Faculty@123"), "Demo Faculty", "faculty"),
            ).fetchone()["id"]
            demo_students = [
                ("26XW5A0501", "Aarav Kumar"), ("26XW5A0502", "Ananya Reddy"),
                ("26XW5A0503", "Rahul Sharma"), ("26XW5A0504", "Priya Naidu"),
                ("26XW5A0505", "Kiran Rao"), ("26XW5A0506", "Sana Begum"),
                ("26XW5A0507", "Vikram Singh"), ("26XW5A0508", "Meghana Das"),
            ]
            for roll, name in demo_students:
                con.execute(
                    """INSERT INTO users(username,password_hash,full_name,role,roll_no,branch,year,section)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (roll.lower(), generate_password_hash("Student@123"), name, "student", roll,
                     "CSE (AI & ML)", "2nd Year", "A"),
                )
            con.execute(
                """INSERT INTO subjects(code,name,branch,year,section,faculty_id)
                   VALUES(?,?,?,?,?,?)""",
                ("AIML201", "Artificial Intelligence", "CSE (AI & ML)", "2nd Year", "A", faculty_id),
            )
            con.execute(
                """INSERT INTO subjects(code,name,branch,year,section,faculty_id)
                   VALUES(?,?,?,?,?,?)""",
                ("DBMS202", "Database Management Systems", "CSE (AI & ML)", "2nd Year", "A", faculty_id),
            )


def current_user():
    if "user_id" not in session:
        return None
    with connect() as con:
        row = con.execute("SELECT id,username,full_name,role,roll_no,branch,year,section FROM users WHERE id=?",
                          (session["user_id"],)).fetchone()
        return dict(row) if row else None

def login_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error":"Please log in first."}), 401
            if roles and user["role"] not in roles:
                return jsonify({"error":"You do not have permission for this action."}), 403
            return fn(*args, **kwargs)
        return wrapped
    return deco

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    with connect() as con:
        row = con.execute("SELECT * FROM users WHERE username=?", (data.get("username","").strip().lower(),)).fetchone()
    if not row or not check_password_hash(row["password_hash"], data.get("password","")):
        return jsonify({"error":"Invalid username or password."}), 401
    session.clear()
    session["user_id"] = row["id"]
    return jsonify({"user": current_user()})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok":True})

@app.route("/api/me")
def me():
    user = current_user()
    return jsonify({"user":user})

@app.route("/api/dashboard")
@login_required()
def dashboard():
    user = current_user()
    with connect() as con:
        if user["role"] == "student":
            total = con.execute("SELECT COUNT(*) n FROM attendance WHERE student_id=?", (user["id"],)).fetchone()["n"]
            present = con.execute("SELECT COUNT(*) n FROM attendance WHERE student_id=? AND status='Present'", (user["id"],)).fetchone()["n"]
            records = con.execute("""SELECT a.attendance_date,a.status,s.code,s.name FROM attendance a
                JOIN subjects s ON s.id=a.subject_id WHERE a.student_id=? ORDER BY a.attendance_date DESC,a.id DESC LIMIT 30""",
                (user["id"],)).fetchall()
            return jsonify({"user":user,"total":total,"present":present,"absent":total-present,
                            "percentage":round(present*100/total,1) if total else 0,"records":[dict(r) for r in records]})
        if user["role"] == "faculty":
            subjects = con.execute("SELECT * FROM subjects WHERE faculty_id=? ORDER BY name", (user["id"],)).fetchall()
            total = con.execute("SELECT COUNT(*) n FROM attendance WHERE marked_by=?", (user["id"],)).fetchone()["n"]
            return jsonify({"user":user,"subjects":[dict(s) for s in subjects],"marked_records":total})
        students = con.execute("SELECT COUNT(*) n FROM users WHERE role='student'").fetchone()["n"]
        faculty = con.execute("SELECT COUNT(*) n FROM users WHERE role='faculty'").fetchone()["n"]
        subjects = con.execute("SELECT COUNT(*) n FROM subjects").fetchone()["n"]
        sessions = con.execute("SELECT COUNT(DISTINCT subject_id || '|' || attendance_date) n FROM attendance").fetchone()["n"]
        return jsonify({"user":user,"students":students,"faculty":faculty,"subjects":subjects,"sessions":sessions})

@app.route("/api/subjects")
@login_required("faculty","admin")
def get_subjects():
    user = current_user()
    with connect() as con:
        if user["role"] == "admin":
            rows = con.execute("SELECT s.*,u.full_name faculty_name FROM subjects s LEFT JOIN users u ON u.id=s.faculty_id ORDER BY s.branch,s.year,s.name").fetchall()
        else:
            rows = con.execute("SELECT * FROM subjects WHERE faculty_id=? ORDER BY name", (user["id"],)).fetchall()
    return jsonify({"subjects":[dict(r) for r in rows]})

@app.route("/api/students")
@login_required("faculty","admin")
def get_students():
    user = current_user()
    subject_id = request.args.get("subject_id", type=int)
    with connect() as con:
        if subject_id:
            subject = con.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
            if not subject:
                return jsonify({"error":"Subject not found."}), 404
            if user["role"] == "faculty" and subject["faculty_id"] != user["id"]:
                return jsonify({"error":"This subject is not assigned to you."}), 403
            rows = con.execute("""SELECT id,full_name,roll_no,branch,year,section FROM users
                WHERE role='student' AND branch=? AND year=? AND section=? ORDER BY roll_no""",
                (subject["branch"],subject["year"],subject["section"])).fetchall()
        else:
            rows = con.execute("""SELECT id,full_name,roll_no,branch,year,section FROM users
                WHERE role='student' ORDER BY branch,year,section,roll_no""").fetchall()
    return jsonify({"students":[dict(r) for r in rows]})

@app.route("/api/attendance", methods=["GET"])
@login_required("faculty","admin")
def get_attendance():
    user = current_user()
    subject_id = request.args.get("subject_id", type=int)
    day = request.args.get("date", date.today().isoformat())
    if not subject_id:
        return jsonify({"error":"Choose a subject."}), 400
    with connect() as con:
        subject = con.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
        if not subject:
            return jsonify({"error":"Subject not found."}), 404
        if user["role"] == "faculty" and subject["faculty_id"] != user["id"]:
            return jsonify({"error":"This subject is not assigned to you."}), 403
        students = con.execute("""SELECT u.id,u.full_name,u.roll_no,a.status FROM users u
            LEFT JOIN attendance a ON a.student_id=u.id AND a.subject_id=? AND a.attendance_date=?
            WHERE u.role='student' AND u.branch=? AND u.year=? AND u.section=? ORDER BY u.roll_no""",
            (subject_id,day,subject["branch"],subject["year"],subject["section"])).fetchall()
    return jsonify({"students":[dict(s) for s in students],"date":day})

@app.route("/api/attendance", methods=["POST"])
@login_required("faculty","admin")
def save_attendance():
    user = current_user()
    data = request.get_json(force=True)
    subject_id = data.get("subject_id")
    day = data.get("date")
    marks = data.get("marks", [])
    try:
        date.fromisoformat(day)
    except (TypeError, ValueError):
        return jsonify({"error":"Enter a valid date."}), 400
    if not subject_id or not isinstance(marks,list) or not marks:
        return jsonify({"error":"Choose a subject and mark at least one student."}), 400
    with connect() as con:
        subject = con.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
        if not subject:
            return jsonify({"error":"Subject not found."}), 404
        if user["role"] == "faculty" and subject["faculty_id"] != user["id"]:
            return jsonify({"error":"This subject is not assigned to you."}), 403
        valid_ids = {r["id"] for r in con.execute("""SELECT id FROM users WHERE role='student'
            AND branch=? AND year=? AND section=?""",
            (subject["branch"],subject["year"],subject["section"])).fetchall()}
        for mark in marks:
            student_id = mark.get("student_id")
            status = mark.get("status")
            if student_id not in valid_ids or status not in ("Present","Absent"):
                return jsonify({"error":"Invalid student or attendance status."}), 400
        for mark in marks:
            con.execute("""INSERT INTO attendance(student_id,subject_id,attendance_date,status,marked_by)
                VALUES(?,?,?,?,?) ON CONFLICT(student_id,subject_id,attendance_date)
                DO UPDATE SET status=excluded.status,marked_by=excluded.marked_by""",
                (mark["student_id"],subject_id,day,mark["status"],user["id"]))
        con.commit()
    return jsonify({"ok":True,"saved":len(marks)})

@app.route("/api/admin/students", methods=["POST"])
@login_required("admin")
def add_student():
    data = request.get_json(force=True)
    required = ["roll_no","full_name","branch","year","section","password"]
    if any(not str(data.get(k,"")).strip() for k in required):
        return jsonify({"error":"Fill in all student fields."}), 400
    if data["branch"] not in BRANCHES:
        return jsonify({"error":"Choose a valid branch."}), 400
    username = data["roll_no"].strip().lower()
    try:
        with connect() as con:
            con.execute("""INSERT INTO users(username,password_hash,full_name,role,roll_no,branch,year,section)
                VALUES(?,?,?,?,?,?,?,?)""",
                (username,generate_password_hash(data["password"]),data["full_name"].strip(),"student",
                 data["roll_no"].strip().upper(),data["branch"],data["year"],data["section"].strip().upper()))
            con.commit()
        return jsonify({"ok":True,"username":username})
    except INTEGRITY_ERRORS:
        return jsonify({"error":"That username or roll number already exists."}), 409

@app.route("/api/admin/faculty", methods=["POST"])
@login_required("admin")
def add_faculty():
    data = request.get_json(force=True)
    if not all(str(data.get(k,"")).strip() for k in ["username","full_name","password"]):
        return jsonify({"error":"Fill in all faculty fields."}), 400
    try:
        with connect() as con:
            con.execute("INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,'faculty')",
                (data["username"].strip().lower(),generate_password_hash(data["password"]),data["full_name"].strip()))
            con.commit()
        return jsonify({"ok":True})
    except INTEGRITY_ERRORS:
        return jsonify({"error":"Username already exists."}), 409

@app.route("/api/admin/subjects", methods=["POST"])
@login_required("admin")
def add_subject():
    data = request.get_json(force=True)
    required = ["code","name","branch","year","section"]
    if any(not str(data.get(k,"")).strip() for k in required) or data.get("branch") not in BRANCHES:
        return jsonify({"error":"Fill all fields and choose a valid branch."}), 400
    faculty_id = data.get("faculty_id") or None
    try:
        with connect() as con:
            con.execute("""INSERT INTO subjects(code,name,branch,year,section,faculty_id)
                VALUES(?,?,?,?,?,?)""",
                (data["code"].strip().upper(),data["name"].strip(),data["branch"],data["year"],
                 data["section"].strip().upper(),faculty_id))
            con.commit()
        return jsonify({"ok":True})
    except INTEGRITY_ERRORS:
        return jsonify({"error":"Could not save subject. Check faculty selection."}), 400

@app.route("/api/admin/users")
@login_required("admin")
def admin_users():
    with connect() as con:
        students = con.execute("SELECT id,full_name,username,roll_no,branch,year,section FROM users WHERE role='student' ORDER BY roll_no").fetchall()
        faculty = con.execute("SELECT id,full_name,username FROM users WHERE role='faculty' ORDER BY full_name").fetchall()
    return jsonify({"students":[dict(r) for r in students],"faculty":[dict(r) for r in faculty]})

@app.route("/api/reports.csv")
@login_required("admin","faculty")
def report_csv():
    user = current_user()
    subject_id = request.args.get("subject_id", type=int)
    start = request.args.get("start", "2000-01-01")
    end = request.args.get("end", "2099-12-31")
    query = """SELECT u.roll_no,u.full_name,u.branch,u.year,u.section,s.code,s.name,
               a.attendance_date,a.status FROM attendance a
               JOIN users u ON u.id=a.student_id JOIN subjects s ON s.id=a.subject_id
               WHERE a.attendance_date BETWEEN ? AND ?"""
    params = [start,end]
    if subject_id:
        query += " AND s.id=?"; params.append(subject_id)
    if user["role"] == "faculty":
        query += " AND s.faculty_id=?"; params.append(user["id"])
    query += " ORDER BY a.attendance_date DESC,s.name,u.roll_no"
    with connect() as con:
        rows = con.execute(query,params).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll Number","Student Name","Branch","Year","Section","Subject Code","Subject","Date","Status"])
    writer.writerows([[r[key] for key in ("roll_no", "full_name", "branch", "year", "section", "code", "name", "attendance_date", "status")] for r in rows])
    from flask import Response
    return Response("\ufeff"+output.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition":"attachment; filename=attendance-report.csv"})

@app.route("/api/branches")
def branches():
    return jsonify({"branches":BRANCHES,"years":["1st Year","2nd Year","3rd Year","4th Year"]})

if __name__ == "__main__":
    init_db()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
