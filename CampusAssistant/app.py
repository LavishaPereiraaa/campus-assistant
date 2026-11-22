from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.utils import secure_filename
from datetime import datetime
from urllib.parse import unquote
import os

# Load .env (optional)
def _load_dotenv_manual() -> None:
    env_path = os.path.join(os.path.dirname(__file__), ".env.local")
    if not os.path.exists(env_path):
        env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    _load_dotenv_manual()

from database.db import connect_db
from database.init_db import init_db

def ensure_notifications_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id VARCHAR(50) NOT NULL,
            department VARCHAR(100),
            message VARCHAR(500) NOT NULL,
            is_read TINYINT(1) NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_notifications_student (student_id, is_read)
        )
    """)


def notify_if_failed(cursor, student_id, department, subject_name, marks, max_marks=100, pass_mark=35):
    """Insert a notification for the student if the given marks count as a fail.

    Avoids duplicate spam: only inserts if there isn't already an unread
    notification for this exact student+subject.
    """
    try:
        if marks is None or marks >= pass_mark:
            return
        ensure_notifications_table(cursor)
        cursor.execute(
            """
            SELECT id FROM notifications
            WHERE student_id=%s AND message LIKE %s AND is_read=0
            """,
            (student_id, f"%{subject_name}%")
        )
        if cursor.fetchone():
            return  # already notified and student hasn't read it yet

        message = f"You have failed in {subject_name} (scored {marks}/{max_marks}). Please contact your department."
        cursor.execute(
            """
            INSERT INTO notifications (student_id, department, message, is_read)
            VALUES (%s, %s, %s, 0)
            """,
            (student_id, department, message)
        )
    except Exception as e:
        print(f"Notification error: {e}")


app = Flask(__name__)
app.secret_key = 'campus_secret_key'
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        password = request.form['password']
        gender = request.form['gender']
        dob = request.form['dob']
        email = request.form['email']
        department = request.form.get('department', 'Computer Science')

        image_path = ""
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{student_id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f"uploads/{filename}"

        conn = connect_db()
        try:
            cursor = conn.cursor()

            # Prevent UNIQUE constraint crash on repeated registrations
            cursor.execute(
                "SELECT 1 FROM registration_requests WHERE student_id=%s",
                (student_id,)
            )
            exists_pending = cursor.fetchone() is not None

            cursor.execute(
                "SELECT 1 FROM approved_students WHERE student_id=%s",
                (student_id,)
            )
            exists_approved = cursor.fetchone() is not None

            if exists_pending or exists_approved:
                # Friendly response (template already supports success, we add duplicate handling)
                return render_template('register.html', success=False, duplicate=True)

            cursor.execute("""
                INSERT INTO registration_requests
                (student_id, name, password, gender, date_of_birth, email, image_path, department, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (student_id, name, password, gender, dob, email, image_path, department))
            conn.commit()
        finally:
            conn.close()

        return render_template('register.html', success=True)

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']

        conn = connect_db()
        try:
            cursor = conn.cursor()

            # 1) Check exact match
            cursor.execute(
                "SELECT * FROM approved_students WHERE student_id=%s AND password=%s",
                (student_id, password)
            )
            user = cursor.fetchone()

            if user:
                session['user'] = user[2]
                session['student_id'] = user[1]
                session['department'] = "Computer Science"
                return redirect('/dashboard')

            # 2) No match: determine whether student_id exists
            cursor.execute(
                "SELECT 1 FROM approved_students WHERE student_id=%s LIMIT 1",
                (student_id,)
            )
            id_exists = cursor.fetchone() is not None

            from flask import flash
            if not id_exists:
                flash("Invalid login: Wrong student id", "error")
            else:
                flash("Invalid login: Password wrong", "error")

        finally:
            conn.close()

    return render_template('login.html')





@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    student_id = session.get('student_id')
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT name, email, image_path, department, gender, date_of_birth FROM approved_students WHERE student_id=%s', (student_id,))
        student = cursor.fetchone()

        notifications = []
        unread_count = 0
        try:
            ensure_notifications_table(cursor)
            cursor.execute(
                "SELECT id, message, is_read, created_at FROM notifications WHERE student_id=%s ORDER BY created_at DESC LIMIT 20",
                (student_id,)
            )
            notifications = [
                {"id": r[0], "message": r[1], "is_read": bool(r[2]), "created_at": r[3]}
                for r in cursor.fetchall()
            ]
            unread_count = sum(1 for n in notifications if not n["is_read"])
        except Exception as e:
            print(f"Notifications load error: {e}")
    finally:
        conn.close()

    return render_template('dashboard.html', user=session['user'], student=student,
                            notifications=notifications, unread_count=unread_count)


@app.route('/notifications/mark-read/<int:notif_id>', methods=['POST'])
def notifications_mark_read(notif_id: int):
    if 'user' not in session:
        return redirect('/login')
    student_id = session.get('student_id')
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE notifications SET is_read=1 WHERE id=%s AND student_id=%s",
            (notif_id, student_id)
        )
        conn.commit()
    finally:
        conn.close()
    return redirect('/dashboard')


@app.route('/notifications/mark-all-read', methods=['POST'])
def notifications_mark_all_read():
    if 'user' not in session:
        return redirect('/login')
    student_id = session.get('student_id')
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE notifications SET is_read=1 WHERE student_id=%s",
            (student_id,)
        )
        conn.commit()
    finally:
        conn.close()
    return redirect('/dashboard')

@app.route('/attendance')
def attendance():
    if 'user' not in session:
        return redirect('/login')

    semester = request.args.get('semester', '')
    student_id = session.get('student_id')
    department = session.get('department', 'Computer Science')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get student's department if available
        cursor.execute("SELECT department FROM approved_students WHERE student_id=%s", (student_id,))
        result = cursor.fetchone()
        if result:
            department = result[0]

        # Get all semesters attendance data
        all_semesters_data = {}
        if student_id:
            for sem in [1, 2, 3, 4]:
                # Get subjects for this semester
                sem_subjects_dict = {}
                cursor.execute("""
                    SELECT id, subject_name, subject_code FROM semester_subjects
                    WHERE department=%s AND semester_number=%s
                    ORDER BY subject_name
                """, (department, sem))
                for row in cursor.fetchall():
                    sem_subjects_dict[row[1].strip()] = row

                # Get per-subject attendance from student_attendance_records
                cursor.execute("""
                    SELECT subject, attendance_percent, attendance_date
                    FROM student_attendance_records
                    WHERE student_id=%s AND semester_number=%s AND department=%s
                    ORDER BY subject
                """, (student_id, sem, department))
                sem_records = cursor.fetchall()
                sem_att_data = {}
                for r in sem_records:
                    sem_att_data[r[0].strip()] = {'percent': r[1], 'date': r[2]}
                    if r[0].strip() not in sem_subjects_dict:
                        sem_subjects_dict[r[0].strip()] = (0, r[0].strip(), '')

                sem_avg = 0
                if sem_records:
                    sem_avg = round(sum(r[1] for r in sem_records) / len(sem_records), 1)

                all_semesters_data[sem] = {
                    'subjects': list(sem_subjects_dict.values()),
                    'attendance_data': sem_att_data,
                    'avg': sem_avg,
                    'status': "PASS" if sem_avg >= 70 else "FAIL" if sem_avg > 0 else "-"
                }

        # Current semester data
        subjects = []
        records = []
        attendance_data = {}
        avg_attendance = 0
        if semester:
            sem_data = all_semesters_data.get(int(semester), {})
            subjects = sem_data.get('subjects', [])
            attendance_data = sem_data.get('attendance_data', {})
            records = [(k, v['percent']) for k, v in attendance_data.items()]
            avg_attendance = sem_data.get('avg', 0)

    finally:
        conn.close()

    return render_template('attendance.html',
        user=session['user'],
        records=records,
        subjects=subjects,
        semester=semester,
        department=department,
        avg_attendance=avg_attendance,
        all_semesters_data=all_semesters_data,
        attendance_data=attendance_data)

@app.route('/timetable')
def timetable():
    if 'user' not in session:
        return redirect('/login')

    semester = request.args.get('semester', '')
    student_id = session.get('student_id')
    department = session.get('department', 'Computer Science')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get student's department
        cursor.execute("SELECT department FROM approved_students WHERE student_id=%s", (student_id,))
        result = cursor.fetchone()
        if result:
            department = result[0]

        # Get timetable entries for the semester
        if semester:
            cursor.execute("""
                SELECT day, subject FROM timetable_entries
                WHERE department=%s AND semester_number=%s
                ORDER BY FIELD(day, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'), id
            """, (department, semester))
            rows = cursor.fetchall()
        else:
            rows = []

        # Get subjects for the semester
        if semester:
            cursor.execute("""
                SELECT subject_name, subject_code FROM semester_subjects
                WHERE department=%s AND semester_number=%s
                ORDER BY subject_name
            """, (department, semester))
            subjects = cursor.fetchall()
        else:
            subjects = []

    finally:
        conn.close()

    return render_template('timetable.html',
        user=session['user'],
        records=rows,
        subjects=subjects,
        semester=semester,
        department=department)

@app.route('/exam')
def exam():
    if 'user' not in session:
        return redirect('/login')

    semester = request.args.get('semester', '')
    student_id = session.get('student_id')
    department = session.get('department', 'Computer Science')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get student's department
        cursor.execute("SELECT department FROM approved_students WHERE student_id=%s", (student_id,))
        result = cursor.fetchone()
        if result:
            department = result[0]

        # Get exam schedule for the semester
        if semester:
            cursor.execute("""
                SELECT subject, exam_date FROM exam_schedule
                WHERE department=%s AND semester_number=%s
                ORDER BY exam_date
            """, (department, semester))
            rows = cursor.fetchall()
        else:
            rows = []

        # Get subjects for the semester
        if semester:
            cursor.execute("""
                SELECT subject_name, subject_code FROM semester_subjects
                WHERE department=%s AND semester_number=%s
                ORDER BY subject_name
            """, (department, semester))
            subjects = cursor.fetchall()
        else:
            subjects = []

    finally:
        conn.close()

    return render_template('exam.html',
        user=session['user'],
        records=rows,
        subjects=subjects,
        semester=semester,
        department=department,
        today_date=datetime.now().strftime('%Y-%m-%d'))

@app.route('/placement')
def placement():
    if 'user' not in session:
        return redirect('/login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT company, package FROM placements WHERE department='Computer Science' ORDER BY id"
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return render_template('placement.html', user=session['user'], records=rows)

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')


@app.route('/student-chatbot')
def student_chatbot():
    if 'user' not in session:
        return redirect('/login')
    return render_template('student_chatbot.html')


@app.route('/department-chatbot')
def department_chatbot():
    if not session.get('admin'):
        return redirect('/department-login')
    return render_template('department_chatbot.html')


# --------------------------------------------
# Chatbot core (AJAX JSON API)
# --------------------------------------------
from chatbot_core.blueprint import bp as chatbot_core_bp

app.register_blueprint(chatbot_core_bp)



# Legacy server-rendered chatbot routes removed.
# Chat is now handled by JSON endpoints under /api/chat/*.


# Department Login
@app.route('/department-login', methods=['GET', 'POST'])
def department_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == "admin" and password == "admin123":
            session['admin'] = True
            return redirect('/department-dashboard')

        from flask import flash
        flash("Invalid department login", "error")

    return render_template('department_login.html')


@app.route('/department-dashboard')
def department_dashboard():
    """Department dashboard shell (DataTables loads rows via AJAX)."""
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, student_id, name, email, department, gender, date_of_birth, image_path, status "
            "FROM registration_requests WHERE status='pending' ORDER BY created_at DESC"
        )
        requests = cursor.fetchall()

        # Fetch richer student profile for department dashboard UI
        # NOTE: Keep backend functionality intact; only extend SELECT for missing UI fields.
        cursor.execute(
            """
            SELECT
                s.student_id,
                s.name,
                s.email,
                s.department,
                s.gender,
                s.date_of_birth,
                s.image_path,
                NULL AS usn,
                NULL AS semester,
                NULL AS phone,
                NULL AS attendance,
                NULL AS cgpa,
                NULL AS status
            FROM approved_students s
            ORDER BY s.name
            """
        )
        students = cursor.fetchall()

    finally:
        conn.close()

    return render_template('department_dashboard.html', requests=requests, students=students)




@app.route('/department-approve/<int:request_id>')
def department_approve(request_id):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        # Get the request
        cursor.execute("SELECT * FROM registration_requests WHERE id=%s", (request_id,))
        req = cursor.fetchone()

        if req:
            # Insert into approved_students
            cursor.execute("""
                INSERT INTO approved_students (student_id, name, password, gender, date_of_birth, email, image_path, department)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (req[1], req[2], req[3], req[4], req[5], req[6], req[7], req[8]))

            # Update request status
            cursor.execute("UPDATE registration_requests SET status='approved' WHERE id=%s", (request_id,))
            conn.commit()
    finally:
        conn.close()

    return redirect('/department-dashboard')

@app.route('/department-reject/<int:request_id>')
def department_reject(request_id):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE registration_requests SET status='rejected' WHERE id=%s", (request_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect('/department-dashboard')

@app.route('/department-delete-request/<int:request_id>')
def department_delete_request(request_id):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM registration_requests WHERE id=%s", (request_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect('/department-dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# Department CRUD routes
@app.route('/department-attendance')
def department_attendance_list():
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', '')
    semester = request.args.get('semester', '')
    student_id = request.args.get('student_id', '')

    # If no department in URL, try session
    if not department:
        department = session.get('department', '')

    # If still no department, redirect to dashboard
    if not department:
        return redirect('/department-dashboard')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get students for the department
        cursor.execute("""
            SELECT student_id, name FROM approved_students
            WHERE department=%s ORDER BY name
        """, (department,))
        students = cursor.fetchall()

        # Get selected student info and their actual department
        selected_student = None
        actual_department = department
        if student_id:
            cursor.execute("""
                SELECT student_id, name, department FROM approved_students
                WHERE student_id=%s
            """, (student_id,))
            result = cursor.fetchone()
            if result:
                selected_student = (result[0], result[1])
                actual_department = result[2]  # Use student's actual department for all queries

        # If no department found, use URL param or redirect
        if not actual_department:
            actual_department = department

        if not actual_department:
            return redirect('/department-dashboard')

        # Get all semesters attendance data
        all_semesters_data = {}
        if student_id and actual_department:
            for sem in [1, 2, 3, 4]:
                cursor.execute("""
                    SELECT subject, attendance_percent, attendance_date
                    FROM student_attendance_records
                    WHERE student_id=%s AND semester_number=%s AND department=%s
                    ORDER BY subject
                """, (student_id, sem, actual_department))
                sem_records = cursor.fetchall()
                sem_att_data = {}
                for r in sem_records:
                    sem_att_data[r[0].strip()] = {'percent': r[1], 'date': r[2]}

                # Get subjects for this semester
                sem_subjects_dict = {}
                cursor.execute("""
                    SELECT id, subject_name, subject_code FROM semester_subjects
                    WHERE department=%s AND semester_number=%s
                    ORDER BY subject_name
                """, (actual_department, sem))
                for row in cursor.fetchall():
                    sem_subjects_dict[row[1].strip()] = row
                # Also include subjects that have attendance but might not be in semester_subjects
                for row in sem_records:
                    key = row[0].strip()
                    if key not in sem_subjects_dict:
                        sem_subjects_dict[key] = (0, key, '')

                sem_avg = 0
                if sem_records:
                    sem_avg = round(sum(r[1] for r in sem_records) / len(sem_records), 1)

                all_semesters_data[sem] = {
                    'subjects': list(sem_subjects_dict.values()),
                    'attendance_data': sem_att_data,
                    'avg': sem_avg,
                    'status': "PASS" if sem_avg >= 70 else "FAIL" if sem_avg > 0 else "-"
                }

        # Current semester data (for single-semester view)
        attendance_data = {}
        overall_attendance = 0
        status = "-"
        attendance_records = []
        subjects = []
        if student_id and semester and actual_department:
            sem_data = all_semesters_data.get(int(semester), {})
            attendance_data = sem_data.get('attendance_data', {})
            attendance_records = [(k, v['percent'], v['date']) for k, v in attendance_data.items()]
            subjects = sem_data.get('subjects', [])
            overall_attendance = sem_data.get('avg', 0)
            status = sem_data.get('status', "-")

        print(f"[DEBUG] all_semesters_data: { {k: {'subjects_count': len(v['subjects']), 'attendance_data': v['attendance_data']} for k, v in all_semesters_data.items()} }")

    finally:
        conn.close()

    print(f"[DEBUG] RENDER: department={actual_department}, semester={semester}, student_id={student_id}")
    print(f"[DEBUG] RENDER: subjects count={len(subjects)}, attendance_data={attendance_data}")

    return render_template('department_attendance.html',
        department=actual_department,
        semester=semester,
        students=students,
        subjects=subjects,
        selected_student=selected_student,
        student_id=student_id,
        attendance_data=attendance_data,
        overall_attendance=overall_attendance,
        status=status,
        all_semesters_data=all_semesters_data,
        today_date=datetime.now().strftime('%Y-%m-%d'))

@app.route('/department-attendance/create', methods=['POST'])
def department_attendance_create():
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.form['department']
    semester = request.form.get('semester', '')
    attendance_date = request.form.get('attendance_date', datetime.now().strftime('%Y-%m-%d'))
    student_id = request.form.get('student_id', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Save/update attendance for each subject
        for key, value in request.form.items():
            if key.startswith('att_'):
                subject_name = unquote(key[4:])  # Remove 'att_' prefix and decode URL-encoded name
                if value and value.strip():
                    try:
                        percent = int(value)
                        cursor.execute(
                            """
                            INSERT INTO student_attendance_records (department, semester_number, subject, attendance_date, student_id, attendance_percent)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                attendance_percent = VALUES(attendance_percent),
                                attendance_date = VALUES(attendance_date)
                            """,
                            (department, semester, subject_name, attendance_date, student_id, percent)
                        )
                    except ValueError:
                        pass  # Skip invalid values

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        conn.close()

    return redirect(f"/department-attendance?department={department}&semester={semester}&student_id={student_id}")

@app.route('/department-promote-students', methods=['POST'])
def department_promote_students():
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.form['department']
    from_semester = request.form.get('from_semester', '')
    to_semester = request.form.get('to_semester', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get all students in the department
        cursor.execute("""
            SELECT student_id FROM approved_students WHERE department=%s
        """, (department,))
        students = cursor.fetchall()

        # Copy subjects from one semester to another
        if from_semester and to_semester and from_semester != to_semester:
            # Get subjects from source semester
            cursor.execute("""
                SELECT subject_name, subject_code FROM semester_subjects
                WHERE department=%s AND semester_number=%s
            """, (department, from_semester))
            source_subjects = cursor.fetchall()

            # Insert subjects for target semester (ignore duplicates)
            for subj in source_subjects:
                cursor.execute("""
                    INSERT IGNORE INTO semester_subjects (department, semester_number, subject_name, subject_code)
                    VALUES (%s, %s, %s, %s)
                """, (department, to_semester, subj[0], subj[1]))

            conn.commit()

    finally:
        conn.close()

    return redirect(f"/department-attendance?department={department}&semester={to_semester}")

@app.route('/department-attendance/edit/<int:record_id>', methods=['GET'])
def department_attendance_edit(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, department, attendance_date, student_id, attendance_percent
            FROM student_attendance_records
            WHERE id=%s
            """,
            (record_id,)
        )
        record = cursor.fetchone()
    finally:
        conn.close()

    return render_template('department_edit_attendance.html', record=record)

@app.route('/department-attendance/update/<int:record_id>', methods=['POST'])
def department_attendance_update(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.form['department']
    attendance_date = request.form['attendance_date']
    student_id = request.form['student_id']
    attendance_percent = int(request.form['attendance_percent'])

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE student_attendance_records
            SET department=%s, attendance_date=%s, student_id=%s, attendance_percent=%s
            WHERE id=%s
            """,
            (department, attendance_date, student_id, attendance_percent, record_id)
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-attendance?department={department}")

@app.route('/department-attendance/delete/<int:record_id>', methods=['GET'])
def department_attendance_delete(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT department FROM student_attendance_records WHERE id=%s",
            (record_id,)
        )
        row = cursor.fetchone()
        department = row[0] if row else 'Computer Science'

        cursor.execute("DELETE FROM student_attendance_records WHERE id=%s", (record_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-attendance?department={department}")

@app.route('/department-timetable')
def department_timetable_list():
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', 'Computer Science')
    semester = request.args.get('semester', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get students for the department
        cursor.execute("""
            SELECT student_id, name FROM approved_students
            WHERE department=%s ORDER BY name
        """, (department,))
        students = cursor.fetchall()

        # Get subjects for selected semester
        if semester:
            cursor.execute("""
                SELECT id, subject_name, subject_code FROM semester_subjects
                WHERE department=%s AND semester_number=%s
                ORDER BY subject_name
            """, (department, semester))
            subjects = cursor.fetchall()
        else:
            subjects = []

        # Get timetable entries for the semester
        if semester:
            cursor.execute("""
                SELECT id, day, subject FROM timetable_entries
                WHERE department=%s AND semester_number=%s
                ORDER BY FIELD(day, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')
            """, (department, semester))
            records = cursor.fetchall()
        else:
            cursor.execute("""
                SELECT id, day, subject FROM timetable_entries
                WHERE department=%s
                ORDER BY FIELD(day, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')
            """, (department,))
            records = cursor.fetchall()

    finally:
        conn.close()

    return render_template('department_timetable.html',
        department=department,
        semester=semester,
        students=students,
        subjects=subjects,
        records=records)

@app.route('/department-timetable/create', methods=['POST'])
def department_timetable_create():
    if not session.get('admin'):
        return redirect('/department-login')

    dept = request.form['department']
    semester = request.form.get('semester', '')
    day = request.form['day']
    subject = request.form['subject']

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO timetable_entries(department, semester_number, day, subject) VALUES(%s,%s,%s,%s)",
            (dept, semester, day, subject)
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-timetable?department={dept}&semester={semester}")

@app.route('/department-timetable/edit/<int:record_id>', methods=['GET'])
def department_timetable_edit(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, department, day, subject FROM timetable_entries WHERE id=%s",
            (record_id,)
        )
        record = cursor.fetchone()
    finally:
        conn.close()

    return render_template('admin_edit_timetable.html', record=record)

@app.route('/department-timetable/update/<int:record_id>', methods=['POST'])
def department_timetable_update(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    dept = request.form['department']
    day = request.form['day']
    subject = request.form['subject']

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE timetable_entries SET department=%s, day=%s, subject=%s WHERE id=%s",
            (dept, day, subject, record_id)
        )
        conn.commit()
    finally:
        conn.close()

    return redirect('/department-timetable')

@app.route('/department-timetable/delete/<int:record_id>', methods=['GET'])
def department_timetable_delete(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM timetable_entries WHERE id=%s", (record_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect('/department-timetable')

@app.route('/department-exam')
def department_exam_list():
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', 'Computer Science')
    semester = request.args.get('semester', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get students for the department
        cursor.execute("""
            SELECT student_id, name FROM approved_students
            WHERE department=%s ORDER BY name
        """, (department,))
        students = cursor.fetchall()

        # Get subjects for selected semester
        if semester:
            cursor.execute("""
                SELECT id, subject_name, subject_code FROM semester_subjects
                WHERE department=%s AND semester_number=%s
                ORDER BY subject_name
            """, (department, semester))
            subjects = cursor.fetchall()
        else:
            subjects = []

        # Get exam schedule for the semester
        if semester:
            cursor.execute("""
                SELECT id, subject, exam_date FROM exam_schedule
                WHERE department=%s AND semester_number=%s
                ORDER BY exam_date
            """, (department, semester))
            records = cursor.fetchall()
        else:
            cursor.execute("""
                SELECT id, subject, exam_date FROM exam_schedule
                WHERE department=%s
                ORDER BY exam_date
            """, (department,))
            records = cursor.fetchall()

    finally:
        conn.close()

    return render_template('department_exam.html',
        department=department,
        semester=semester,
        subjects=subjects,
        records=records,
        students=students,
        today_date=datetime.now().strftime('%Y-%m-%d'))

@app.route('/department-exam/create', methods=['POST'])
def department_exam_create():
    if not session.get('admin'):
        return redirect('/department-login')

    dept = request.form['department']
    semester = request.form.get('semester', '')
    subject = request.form['subject']
    exam_date = request.form['exam_date']

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO exam_schedule(department, semester_number, subject, exam_date) VALUES(%s,%s,%s,%s)",
            (dept, semester, subject, exam_date)
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-exam?department={dept}&semester={semester}")

    return redirect('/department-exam')

@app.route('/department-exam/edit/<int:record_id>', methods=['GET'])
def department_exam_edit(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, department, subject, exam_date FROM exam_schedule WHERE id=%s",
            (record_id,)
        )
        record = cursor.fetchone()
    finally:
        conn.close()

    return render_template('admin_edit_exam.html', record=record)

@app.route('/department-exam/update/<int:record_id>', methods=['POST'])
def department_exam_update(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    dept = request.form['department']
    subject = request.form['subject']
    exam_date = request.form['exam_date']

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE exam_schedule SET department=%s, subject=%s, exam_date=%s WHERE id=%s",
            (dept, subject, exam_date, record_id)
        )
        conn.commit()
    finally:
        conn.close()

    return redirect('/department-exam')

@app.route('/department-exam/delete/<int:record_id>', methods=['GET'])
def department_exam_delete(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM exam_schedule WHERE id=%s", (record_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect('/department-exam')

@app.route('/department-placement')
def department_placement_list():
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, department, company, package FROM placements ORDER BY id")
        records = cursor.fetchall()
    finally:
        conn.close()

    return render_template('department_placement.html', records=records)

@app.route('/department-placement/create', methods=['POST'])
def department_placement_create():
    if not session.get('admin'):
        return redirect('/department-login')

    dept = request.form['department']
    company = request.form['company']
    package = request.form['package']

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO placements(department, company, package) VALUES(%s,%s,%s)",
            (dept, company, package)
        )
        conn.commit()
    finally:
        conn.close()

    return redirect('/department-placement')

@app.route('/department-placement/edit/<int:record_id>', methods=['GET'])
def department_placement_edit(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, department, company, package FROM placements WHERE id=%s",
            (record_id,)
        )
        record = cursor.fetchone()
    finally:
        conn.close()

    return render_template('admin_edit_placement.html', record=record)

@app.route('/department-placement/update/<int:record_id>', methods=['POST'])
def department_placement_update(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    dept = request.form['department']
    company = request.form['company']
    package = request.form['package']

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE placements SET department=%s, company=%s, package=%s WHERE id=%s",
            (dept, company, package, record_id)
        )
        conn.commit()
    finally:
        conn.close()

    return redirect('/department-placement')

@app.route('/department-placement/delete/<int:record_id>', methods=['GET'])
def department_placement_delete(record_id: int):
    if not session.get('admin'):
        return redirect('/department-login')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM placements WHERE id=%s", (record_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect('/department-placement')

# ============================================
# RESULT MANAGEMENT ROUTES
# ============================================

@app.route('/department-result', methods=['GET'])
def department_result():
    """Main result management page for department"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', '')
    semester = request.args.get('semester', '')
    student_id = request.args.get('student_id', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get students for the department
        students = []
        if department:
            cursor.execute(
                "SELECT student_id, name FROM approved_students WHERE department=%s ORDER BY name",
                (department,)
            )
            students = cursor.fetchall()

        # Get selected student info (must belong to the department)
        selected_student = None
        if student_id and department:
            cursor.execute("SELECT student_id, name FROM approved_students WHERE student_id=%s AND department=%s", (student_id, department))
            result = cursor.fetchone()
            if result:
                selected_student = result

        # Get subjects for department and semester
        subjects = []
        if department and semester:
            cursor.execute("""
                SELECT id, department, subject_name, subject_code
                FROM semester_subjects
                WHERE department=%s AND semester_number=%s
                ORDER BY subject_name
            """, (department, semester))
            subjects = cursor.fetchall()

        # Get student's marks for this semester
        student_results = []
        total_marks = 0
        average = 0
        status = "-"
        attendance_percent = None
        if student_id and semester:
            cursor.execute("""
                SELECT sr.id, sr.subject_name, sr.marks, sr.max_marks
                FROM student_results sr
                WHERE sr.student_id=%s AND sr.semester_number=%s
                ORDER BY sr.subject_name
            """, (student_id, semester))
            student_results = cursor.fetchall()

            # Get student's average attendance for this semester
            cursor.execute("""
                SELECT AVG(attendance_percent)
                FROM student_attendance_records
                WHERE student_id=%s AND semester_number=%s AND department=%s
            """, (student_id, semester, department))
            att_row = cursor.fetchone()
            attendance_percent = round(att_row[0], 1) if att_row and att_row[0] else 0

            if student_results:
                total_obtained = sum(r[2] for r in student_results)
                total_max = sum(r[3] for r in student_results)
                total_marks = f"{total_obtained}/{total_max}"
                average = round((total_obtained / total_max) * 100, 1) if total_max > 0 else 0
                # Fail if any subject < 35 OR attendance < 70%
                all_passed = all(r[2] >= 35 for r in student_results)
                status = "PASS" if all_passed and attendance_percent >= 70 else "FAIL"

    finally:
        conn.close()

    return render_template(
        'department_result.html',
        department=department,
        semester=semester,
        students=students,
        subjects=subjects,
        selected_student=selected_student,
        student_id=student_id,
        student_results=student_results,
        total_marks=total_marks,
        average=average,
        status=status,
        attendance_percent=attendance_percent
    )


@app.route('/department-subjects', methods=['GET'])
def department_subjects():
    """Department subject management page"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', '')
    semester = request.args.get('semester', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get subjects for department and semester
        subjects = []
        if department and semester:
            cursor.execute("""
                SELECT id, department, semester_number, subject_name, subject_code
                FROM semester_subjects
                WHERE department=%s AND semester_number=%s
                ORDER BY subject_name
            """, (department, semester))
            subjects = cursor.fetchall()

    finally:
        conn.close()

    return render_template('department_subjects.html',
        department=department,
        semester=semester,
        subjects=subjects
    )

@app.route('/department-subjects/add', methods=['POST'])
def department_subjects_add():
    """Add a new subject"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.form['department']
    semester = request.form['semester']
    subject_name = request.form['subject_name']
    subject_code = request.form.get('subject_code', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO semester_subjects (department, semester_number, subject_name, subject_code)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE subject_code = VALUES(subject_code)
        """, (department, semester, subject_name, subject_code))
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-subjects?department={department}&semester={semester}")

@app.route('/department-subjects/seed', methods=['GET'])
def department_subjects_seed():
    """Seed default subjects for all semesters"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', '')
    if not department:
        return redirect('/department-subjects')

    default_subjects = {
        1: [
            ("CS101", "Mathematics-I"),
            ("CS102", "Physics"),
            ("CS103", "Chemistry"),
            ("CS104", "Computer Science Fundamentals"),
            ("CS105", "English Communications"),
        ],
        2: [
            ("CS201", "Mathematics-II"),
            ("CS202", "Digital Electronics"),
            ("CS203", "Programming in C"),
            ("CS204", "Data Structures"),
            ("CS205", "Technical Writing"),
        ],
        3: [
            ("CS301", "Database Management"),
            ("CS302", "Operating Systems"),
            ("CS303", "Computer Networks"),
            ("CS304", "Web Technologies"),
            ("CS305", "Software Engineering"),
        ],
        4: [
            ("CS401", "Artificial Intelligence"),
            ("CS402", "Machine Learning"),
            ("CS403", "Cloud Computing"),
            ("CS404", "Cyber Security"),
            ("CS405", "Project Management"),
        ],
    }

    conn = connect_db()
    try:
        cursor = conn.cursor()
        for semester, subjects in default_subjects.items():
            for code, name in subjects:
                # Check if subject already exists by department + semester + code
                cursor.execute("""
                    SELECT id FROM semester_subjects
                    WHERE department=%s AND semester_number=%s AND subject_code=%s
                """, (department, semester, code))
                existing = cursor.fetchone()
                if existing:
                    # Update existing subject name
                    cursor.execute("""
                        UPDATE semester_subjects SET subject_name=%s WHERE id=%s
                    """, (name, existing[0]))
                else:
                    # Insert new subject
                    cursor.execute("""
                        INSERT INTO semester_subjects (department, semester_number, subject_name, subject_code)
                        VALUES (%s, %s, %s, %s)
                    """, (department, semester, name, code))
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-subjects?department={department}&semester=1")

@app.route('/department-subjects/delete/<int:subject_id>', methods=['GET'])
def department_subjects_delete(subject_id: int):
    """Delete a subject"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', '')
    semester = request.args.get('semester', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM semester_subjects WHERE id=%s", (subject_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-subjects?department={department}&semester={semester}")

@app.route('/department-subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
def department_subjects_edit(subject_id: int):
    """Edit a subject"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', '')
    semester = request.args.get('semester', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        if request.method == 'POST':
            subject_name = request.form['subject_name']
            subject_code = request.form.get('subject_code', '')
            cursor.execute("""
                UPDATE semester_subjects SET subject_name=%s, subject_code=%s WHERE id=%s
            """, (subject_name, subject_code, subject_id))
            conn.commit()
            return redirect(f"/department-subjects?department={department}&semester={semester}")

        # GET request - check for inline edit with code/name params
        code = request.args.get('code')
        name = request.args.get('name')
        if code is not None and name is not None:
            cursor.execute("""
                UPDATE semester_subjects SET subject_name=%s, subject_code=%s WHERE id=%s
            """, (name, code, subject_id))
            conn.commit()
            return redirect(f"/department-subjects?department={department}&semester={semester}")

        # GET request - get subject data
        cursor.execute("""
            SELECT id, department, semester_number, subject_name, subject_code
            FROM semester_subjects WHERE id=%s
        """, (subject_id,))
        subject = cursor.fetchone()

    finally:
        conn.close()

    return render_template('department_subjects_edit.html',
        department=department,
        semester=semester,
        subject=subject
    )


@app.route('/department-result/add-subject', methods=['POST'])
def department_result_add_subject():
    """Add a new subject to a semester"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.form['department']
    semester = request.form['semester']
    subject_name = request.form['subject_name']
    subject_code = request.form.get('subject_code', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO semester_subjects (department, semester_number, subject_name, subject_code)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE subject_code = VALUES(subject_code)
        """, (department, semester, subject_name, subject_code))
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-result?department={department}&semester={semester}")


@app.route('/department-result/edit-subject/<int:record_id>', methods=['GET'])
def department_result_edit_subject(record_id: int):
    """Edit subject page"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', '')
    semester = request.args.get('semester', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, department, semester_number, subject_name, subject_code
            FROM semester_subjects WHERE id=%s
        """, (record_id,))
        record = cursor.fetchone()
    finally:
        conn.close()

    if not record:
        return redirect(f"/department-result?department={department}&semester={semester}")

    return render_template('department_edit_subject.html', record=record, department=department, semester=semester)


@app.route('/department-result/update-subject/<int:record_id>', methods=['POST'])
def department_result_update_subject(record_id: int):
    """Update subject"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.form['department']
    semester = request.form['semester']
    subject_name = request.form['subject_name']
    subject_code = request.form.get('subject_code', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE semester_subjects
            SET subject_name=%s, subject_code=%s
            WHERE id=%s
        """, (subject_name, subject_code, record_id))
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-result?department={department}&semester={semester}")


@app.route('/department-result/delete-subject/<int:record_id>', methods=['GET'])
def department_result_delete_subject(record_id: int):
    """Delete subject"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', '')
    semester = request.args.get('semester', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM semester_subjects WHERE id=%s", (record_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-result?department={department}&semester={semester}")


@app.route('/department-result/save-marks', methods=['POST'])
def department_result_save_marks():
    """Save marks for a student"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.form['department']
    semester = request.form['semester']
    student_id = request.form['student_id']

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get all subjects for this semester
        cursor.execute("""
            SELECT id, subject_name FROM semester_subjects
            WHERE department=%s AND semester_number=%s
        """, (department, semester))
        subjects = cursor.fetchall()

        # Save/update marks for each subject
        for subj in subjects:
            subj_id = subj[0]
            marks_key = f"marks_{subj_id}"
            if marks_key in request.form and request.form[marks_key]:
                marks = int(request.form[marks_key])
                cursor.execute("""
                    INSERT INTO student_results (student_id, department, semester_number, subject_name, marks, max_marks)
                    VALUES (%s, %s, %s, %s, %s, 100)
                    ON DUPLICATE KEY UPDATE marks = VALUES(marks)
                """, (student_id, department, semester, subj[1], marks))
                notify_if_failed(cursor, student_id, department, subj[1], marks, max_marks=100)

        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-result?department={department}&semester={semester}&student_id={student_id}")


@app.route('/department-result/edit-marks/<int:record_id>', methods=['GET'])
def department_result_edit_marks(record_id: int):
    """Edit marks page"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.args.get('department', '')
    semester = request.args.get('semester', '')
    student_id = request.args.get('student_id', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, student_id, department, semester_number, subject_name, marks, max_marks
            FROM student_results WHERE id=%s
        """, (record_id,))
        record = cursor.fetchone()

        # Get student name
        student_name = ""
        if record:
            cursor.execute("SELECT name FROM approved_students WHERE student_id=%s", (record[1],))
            row = cursor.fetchone()
            if row:
                student_name = row[0]
    finally:
        conn.close()

    if not record:
        return redirect(f"/department-result?department={department}&semester={semester}")

    return render_template('department_edit_marks.html', record=record,
        department=department, semester=semester, student_id=student_id, student_name=student_name,
        subject_name=record[4])


@app.route('/department-result/update-marks/<int:record_id>', methods=['POST'])
def department_result_update_marks(record_id: int):
    """Update marks"""
    if not session.get('admin'):
        return redirect('/department-login')

    department = request.form['department']
    semester = request.form['semester']
    student_id = request.form['student_id']
    marks = int(request.form['marks'])
    max_marks = int(request.form['max_marks'])

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT subject_name FROM student_results WHERE id=%s", (record_id,))
        row = cursor.fetchone()
        subject_name = row[0] if row else "a subject"

        cursor.execute("""
            UPDATE student_results SET marks=%s, max_marks=%s WHERE id=%s
        """, (marks, max_marks, record_id))
        notify_if_failed(cursor, student_id, department, subject_name, marks, max_marks=max_marks)
        conn.commit()
    finally:
        conn.close()

    return redirect(f"/department-result?department={department}&semester={semester}&student_id={student_id}")


# ============================================
# STUDENT RESULT PAGE
# ============================================

@app.route('/student-result', methods=['GET'])
def student_result():
    """Student view of their results"""
    if 'user' not in session:
        return redirect('/login')

    student_id = session.get('student_id')
    semester = request.args.get('semester', '')

    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Get student info
        cursor.execute(
            "SELECT id, student_id, name, email, image_path, department, gender, date_of_birth FROM approved_students WHERE student_id=%s",
            (student_id,)
        )
        student = cursor.fetchone()

        results = []
        total_marks = "-"
        average = 0
        status = "-"
        all_semester_results = []
        attendance_percent = None
        student_subjects = []

        if semester:
            # Get results for selected semester
            cursor.execute("""
                SELECT sr.id, sr.student_id, sr.department, sr.semester_number,
                       sr.subject_name, sr.marks, sr.max_marks, ss.subject_code
                FROM student_results sr
                LEFT JOIN semester_subjects ss ON sr.department = ss.department
                    AND sr.semester_number = ss.semester_number
                    AND sr.subject_name = ss.subject_name
                WHERE sr.student_id=%s AND sr.semester_number=%s
                ORDER BY sr.subject_name
            """, (student_id, semester))
            results = cursor.fetchall()

            if results:
                total_obtained = sum(r[5] for r in results)
                total_max = sum(r[6] for r in results)
                total_marks = f"{total_obtained}/{total_max}"
                average = round((total_obtained / total_max) * 100, 1) if total_max > 0 else 0
                # Fail if any subject < 35 OR attendance < 70%
                all_passed = all(r[5] >= 35 for r in results)

                # Get attendance
                # Use student's actual department from student record
                stu_dept = student[5] if student else None
                cursor.execute("""
                    SELECT AVG(attendance_percent)
                    FROM student_attendance_records
                    WHERE student_id=%s AND semester_number=%s AND department=%s
                """, (student_id, semester, stu_dept))
                att_row = cursor.fetchone()
                attendance_percent = round(att_row[0], 1) if att_row and att_row[0] else 0

                # Get subjects with per-subject attendance
                student_subjects = []
                if stu_dept:
                    cursor.execute("""
                        SELECT id, subject_name, subject_code FROM semester_subjects
                        WHERE department=%s AND semester_number=%s
                        ORDER BY subject_name
                    """, (stu_dept, semester))
                    subj_rows = cursor.fetchall()

                    cursor.execute("""
                        SELECT subject, attendance_percent, attendance_date
                        FROM student_attendance_records
                        WHERE student_id=%s AND semester_number=%s AND department=%s
                        ORDER BY subject
                    """, (student_id, semester, stu_dept))
                    att_rows = cursor.fetchall()
                    att_lookup = {r[0].strip(): {'percent': r[1], 'date': r[2]} for r in att_rows}

                    for sr in subj_rows:
                        key = sr[1].strip()
                        att = att_lookup.get(key)
                        student_subjects.append({
                            'name': sr[1],
                            'code': sr[2],
                            'percent': att['percent'] if att else None,
                            'date': att['date'] if att else None
                        })

                    # Also include subjects that have attendance but not in semester_subjects
                    for r in att_rows:
                        key = r[0].strip()
                        if not any(s[1].strip() == key for s in subj_rows):
                            student_subjects.append({
                                'name': key,
                                'code': '-',
                                'percent': r[1],
                                'date': r[2]
                            })

                status = "PASS" if all_passed and attendance_percent >= 70 else "FAIL"

        # Get all semester results for summary
        cursor.execute("""
            SELECT semester_number,
                   SUM(marks) as total_obtained,
                   SUM(max_marks) as total_max,
                   ROUND((SUM(marks) / SUM(max_marks)) * 100, 1) as avg_percent,
                   CASE WHEN SUM(CASE WHEN marks >= 35 THEN 1 ELSE 0 END) = COUNT(*) THEN 'PASS' ELSE 'FAIL' END as status
            FROM student_results
            WHERE student_id=%s
            GROUP BY semester_number
            ORDER BY semester_number
        """, (student_id,))
        all_semester_results = cursor.fetchall()

    finally:
        conn.close()

    return render_template('student_result.html',
        student=student,
        semester=semester,
        results=results,
        total_marks=total_marks,
        average=average,
        status=status,
        all_semester_results=all_semester_results,
        attendance_percent=attendance_percent,
        student_subjects=student_subjects
    )


if __name__ == '__main__':
    app.run(debug=True)