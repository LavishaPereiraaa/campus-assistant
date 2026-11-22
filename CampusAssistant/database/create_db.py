import os
import mysql.connector
from datetime import datetime, timedelta

def _load_env_file(env_path: str) -> None:
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except Exception:
        return

def _ensure_env_loaded() -> None:
    if any(os.getenv(k) for k in ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB")):
        return
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _load_env_file(os.path.join(base_dir, ".env.local"))
    _load_env_file(os.path.join(base_dir, ".env"))

def _get_env(name: str, default: str | None = None) -> str:
    _ensure_env_loaded()
    val = os.getenv(name, default)
    if val is None:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            f"Create a .env.local/.env with MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB."
        )
    return val

def create_database():
    """Create all tables and seed data in MySQL"""
    conn = mysql.connector.connect(
        host=_get_env("MYSQL_HOST"),
        user=_get_env("MYSQL_USER"),
        password=_get_env("MYSQL_PASSWORD"),
        database=_get_env("MYSQL_DB")
    )
    cursor = conn.cursor()

    # Create students table with department
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            department VARCHAR(255) NOT NULL
        )
    """)

    # Create attendance_records table (legacy subject-wise)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            department VARCHAR(255) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            attendance_percent INT NOT NULL
        )
    """)

    # Create student_attendance_records table (new student-wise manual attendance)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_attendance_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            department VARCHAR(255) NOT NULL,
            attendance_date DATE NOT NULL,
            student_id VARCHAR(20) NOT NULL,
            attendance_percent INT NOT NULL,
            UNIQUE KEY uniq_student_attendance (department, attendance_date, student_id)
        )
    """)

    # Create timetable_entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable_entries (
            id INT AUTO_INCREMENT PRIMARY KEY,
            department VARCHAR(255) NOT NULL,
            day VARCHAR(50) NOT NULL,
            subject VARCHAR(255) NOT NULL
        )
    """)

    # Create exam_schedule table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exam_schedule (
            id INT AUTO_INCREMENT PRIMARY KEY,
            department VARCHAR(255) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            exam_date DATE NOT NULL
        )
    """)

    # Create placements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS placements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            department VARCHAR(255) NOT NULL,
            company VARCHAR(255) NOT NULL,
            package VARCHAR(255) NOT NULL
        )
    """)

    conn.commit()
    print("All tables created successfully!")

    # Seed data
    seed_data(cursor, conn)
    conn.close()

def seed_data(cursor, conn) -> None:
    """Seed sample data - 10 entries per department"""
    departments = ["Computer Science", "Electronics", "Mechanical", "Civil", "Electrical"]

    # Clear existing data first
    cursor.execute("TRUNCATE TABLE students")
    cursor.execute("TRUNCATE TABLE attendance_records")
    cursor.execute("TRUNCATE TABLE timetable_entries")
    cursor.execute("TRUNCATE TABLE exam_schedule")
    cursor.execute("TRUNCATE TABLE placements")

    # Students - 10 per department (50 total)
    students = [
        # Computer Science
        ("Rahul Sharma", "rahul.sharma@student.edu", "pass123", "Computer Science"),
        ("Priya Patel", "priya.patel@student.edu", "pass123", "Computer Science"),
        ("Amit Kumar", "amit.kumar@student.edu", "pass123", "Computer Science"),
        ("Sneha Gupta", "sneha.gupta@student.edu", "pass123", "Computer Science"),
        ("Vikram Singh", "vikram.singh@student.edu", "pass123", "Computer Science"),
        ("Ananya Reddy", "ananya.reddy@student.edu", "pass123", "Computer Science"),
        ("Rajesh Verma", "rajesh.verma@student.edu", "pass123", "Computer Science"),
        ("Kavya Nair", "kavya.nair@student.edu", "pass123", "Computer Science"),
        ("Arjun Iyer", "arjun.iyer@student.edu", "pass123", "Computer Science"),
        ("Meera Joshi", "meera.joshi@student.edu", "pass123", "Computer Science"),
        # Electronics
        ("Karthik Rao", "karthik.rao@student.edu", "pass123", "Electronics"),
        ("Divya Shankar", "divya.shankar@student.edu", "pass123", "Electronics"),
        ("Nikhil Prasad", "nikhil.prasad@student.edu", "pass123", "Electronics"),
        ("Lakshmi Menon", "lakshmi.menon@student.edu", "pass123", "Electronics"),
        ("Suresh Babu", "suresh.babu@student.edu", "pass123", "Electronics"),
        ("Geetha Krishnan", "geetha.krishnan@student.edu", "pass123", "Electronics"),
        ("Mohan Das", "mohan.das@student.edu", "pass123", "Electronics"),
        ("Shreya Bhat", "shreya.bhat@student.edu", "pass123", "Electronics"),
        ("Aditya Raj", "aditya.raj@student.edu", "pass123", "Electronics"),
        ("Nisha Verma", "nisha.verma@student.edu", "pass123", "Electronics"),
        # Mechanical
        ("Ravi Kumar", "ravi.kumar@student.edu", "pass123", "Mechanical"),
        ("Pooja Singh", "pooja.singh@student.edu", "pass123", "Mechanical"),
        ("Ajay Patel", "ajay.patel@student.edu", "pass123", "Mechanical"),
        ("Sunita Yadav", "sunita.yadav@student.edu", "pass123", "Mechanical"),
        ("Deepak Rao", "deepak.rao@student.edu", "pass123", "Mechanical"),
        ("Anita Sharma", "anita.sharma@student.edu", "pass123", "Mechanical"),
        ("Vijay Gupta", "vijay.gupta@student.edu", "pass123", "Mechanical"),
        ("Rita Kumari", "rita.kumari@student.edu", "pass123", "Mechanical"),
        ("Sanjay Mishra", "sanjay.mishra@student.edu", "pass123", "Mechanical"),
        ("Kamala Devi", "kamala.devi@student.edu", "pass123", "Mechanical"),
        # Civil
        ("Harish Nair", "harish.nair@student.edu", "pass123", "Civil"),
        ("Madhavi Reddy", "madhavi.reddy@student.edu", "pass123", "Civil"),
        ("Prakash Jha", "prakash.jha@student.edu", "pass123", "Civil"),
        ("Lalitha Krishnan", "lalitha.krishnan@student.edu", "pass123", "Civil"),
        ("Gopal Krishna", "gopal.krishna@student.edu", "pass123", "Civil"),
        ("Sarita Devi", "sarita.devi@student.edu", "pass123", "Civil"),
        ("Murali Venkat", "murali.venkat@student.edu", "pass123", "Civil"),
        ("Pushpa Rani", "pushpa.rani@student.edu", "pass123", "Civil"),
        ("Ramesh Chary", "ramesh.chary@student.edu", "pass123", "Civil"),
        ("Anjali Devi", "anjali.devi@student.edu", "pass123", "Civil"),
        # Electrical
        ("Sathish Kumar", "sathish.kumar@student.edu", "pass123", "Electrical"),
        ("Vasantha Rao", "vasantha.rao@student.edu", "pass123", "Electrical"),
        ("Ravi Teja", "ravi.teja@student.edu", "pass123", "Electrical"),
        ("Padma Priya", "padma.priya@student.edu", "pass123", "Electrical"),
        ("Chetan Patel", "chetan.patel@student.edu", "pass123", "Electrical"),
        ("Manjula Devi", "manjula.devi@student.edu", "pass123", "Electrical"),
        ("Kiran Kumar", "kiran.kumar@student.edu", "pass123", "Electrical"),
        ("Uma Mahesh", "uma.mahesh@student.edu", "pass123", "Electrical"),
        ("Venkat Rao", "venkat.rao@student.edu", "pass123", "Electrical"),
        ("Lakshmi Prasad", "lakshmi.prasad@student.edu", "pass123", "Electrical"),
    ]
    cursor.executemany(
        "INSERT INTO students (name, email, password, department) VALUES (%s, %s, %s, %s)",
        students
    )

    # Attendance - 10 subjects per department
    attendance_subjects = {
        "Computer Science": ["Data Structures", "Operating Systems", "Database Management", "Web Development", "Artificial Intelligence", "Cloud Computing", "Cyber Security", "Machine Learning", "Computer Networks", "Software Engineering"],
        "Electronics": ["Circuit Analysis", "Digital Electronics", "Signal Processing", "Microprocessors", "Communication Systems", "VLSI Design", "Embedded Systems", "Power Electronics", "Control Systems", "Instrumentation"],
        "Mechanical": ["Thermodynamics", "Fluid Mechanics", "Manufacturing Process", "Machine Design", "Automobile Engineering", "Finite Element Analysis", "Robotics", "Heat Transfer", "IC Engines", "Strength of Materials"],
        "Civil": ["Structural Analysis", "Concrete Technology", "Geotechnical Engineering", "Hydrology", "Environmental Engineering", "Highway Engineering", "Surveying", "Steel Design", "Foundation Engineering", "Building Materials"],
        "Electrical": ["Power Systems", "Electrical Machines", "Control Systems", "Power Electronics", "Renewable Energy", "High Voltage Engineering", "Electrical Measurements", "Circuit Theory", "Digital Signal Processing", "Utilization of Electrical Energy"]
    }

    attendance = []
    for dept in departments:
        for idx, subj in enumerate(attendance_subjects[dept]):
            attendance.append((dept, subj, 70 + (idx % 30)))
    cursor.executemany(
        "INSERT INTO attendance_records (department, subject, attendance_percent) VALUES (%s, %s, %s)",
        attendance
    )

    # Timetable - 10 entries per department
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    timetable_subjects = attendance_subjects  # Same subjects

    timetable = []
    for dept in departments:
        for idx, subj in enumerate(timetable_subjects[dept]):
            day = days[idx % 5]
            timetable.append((dept, day, subj))
    cursor.executemany(
        "INSERT INTO timetable_entries (department, day, subject) VALUES (%s, %s, %s)",
        timetable
    )

    # Exams - 10 per department
    base_date = datetime(2026, 6, 10)
    exams = []
    for dept_idx, dept in enumerate(departments):
        for subj_idx, subj in enumerate(timetable_subjects[dept]):
            exam_date = (base_date + timedelta(days=dept_idx * 15 + subj_idx)).strftime("%Y-%m-%d")
            exams.append((dept, subj, exam_date))
    cursor.executemany(
        "INSERT INTO exam_schedule (department, subject, exam_date) VALUES (%s, %s, %s)",
        exams
    )

    # Placements - 10 per department
    placement_data = {
        "Computer Science": [("TCS", "8 LPA"), ("Infosys", "7 LPA"), ("Wipro", "6.5 LPA"), ("Google", "25 LPA"), ("Microsoft", "22 LPA"), ("Amazon", "20 LPA"), ("Flipkart", "14 LPA"), ("Paytm", "12 LPA"), ("Myntra", "10 LPA"), ("HCL", "9 LPA")],
        "Electronics": [("Samsung", "12 LPA"), ("Intel", "15 LPA"), ("Qualcomm", "18 LPA"), ("Texas Instruments", "14 LPA"), ("NVIDIA", "20 LPA"), ("Apple", "19 LPA"), ("Sony", "11 LPA"), ("LG", "13 LPA"), ("Panasonic", "16 LPA"), ("Bosch", "17 LPA")],
        "Mechanical": [("Tata Motors", "8 LPA"), ("Hyundai", "7.5 LPA"), ("Bajaj Auto", "9 LPA"), ("L&T", "10 LPA"), ("Mahindra", "8.5 LPA"), ("Hero MotoCorp", "11 LPA"), ("Maruti Suzuki", "9.5 LPA"), ("Ashok Leyland", "12 LPA"), ("Force Motors", "7 LPA"), ("Eicher", "10.5 LPA")],
        "Civil": [("L&T", "6 LPA"), ("Tata Projects", "7 LPA"), ("GMR", "8 LPA"), ("DLF", "9 LPA"), ("Shapoorji Pallonji", "6.5 LPA"), ("Oberoi Realty", "10 LPA"), ("Lodha", "8.5 LPA"), ("NCC", "7.5 LPA"), ("IRCTC", "5.5 LPA"), ("NBCC", "9.5 LPA")],
        "Electrical": [("NTPC", "7 LPA"), ("Gail", "8 LPA"), ("BHEL", "9 LPA"), ("Power Grid", "10 LPA"), ("Reliance Energy", "12 LPA"), ("Tata Power", "11 LPA"), ("Adani Green", "6.5 LPA"), ("JSW Energy", "13 LPA"), ("Torrent Power", "14 LPA"), ("Crompton", "15 LPA")]
    }

    placements = []
    for dept in departments:
        for company, package in placement_data[dept]:
            placements.append((dept, company, package))
    cursor.executemany(
        "INSERT INTO placements (department, company, package) VALUES (%s, %s, %s)",
        placements
    )

    conn.commit()
    print("Database created and seeded with 50 students, 50 attendance, 50 timetable, 50 exam, and 50 placement records!")

if __name__ == "__main__":
    create_database()
