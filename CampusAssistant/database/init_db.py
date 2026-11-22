from datetime import datetime, timedelta

from database.db import connect_db


def init_db() -> None:
    """Initialize database - create tables and seed data"""
    conn = connect_db()
    try:
        cursor = conn.cursor()

        # Create registration_requests table (pending approvals)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registration_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id VARCHAR(20) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                gender VARCHAR(10),
                date_of_birth DATE,
                email VARCHAR(255) UNIQUE NOT NULL,
                image_path VARCHAR(255),
                department VARCHAR(255) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create approved_students table (approved students)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approved_students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id VARCHAR(20) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                gender VARCHAR(10),
                date_of_birth DATE,
                email VARCHAR(255) UNIQUE NOT NULL,
                image_path VARCHAR(255),
                department VARCHAR(255) NOT NULL,
                approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                semester_number INT NOT NULL,
                subject VARCHAR(255) NOT NULL,
                attendance_date DATE NOT NULL,
                student_id VARCHAR(20) NOT NULL,
                attendance_percent INT NOT NULL,
                UNIQUE KEY uniq_student_attendance (department, semester_number, subject, attendance_date, student_id)
            )
        """)

        # Add missing columns if they don't exist (migration)
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'student_attendance_records' AND COLUMN_NAME = 'semester_number'
            """, (MYSQL_DB,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE student_attendance_records ADD COLUMN semester_number INT AFTER department")
        except:
            pass
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'student_attendance_records' AND COLUMN_NAME = 'subject'
            """, (MYSQL_DB,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE student_attendance_records ADD COLUMN subject VARCHAR(255) AFTER semester_number")
        except:
            pass
        # Drop old unique key and add new one if needed
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'student_attendance_records' AND INDEX_NAME = 'uniq_student_attendance'
            """, (MYSQL_DB,))
            if cursor.fetchone()[0] > 0:
                cursor.execute("ALTER TABLE student_attendance_records DROP INDEX uniq_student_attendance")
        except:
            pass
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'student_attendance_records' AND INDEX_NAME = 'uniq_student_att_new'
            """, (MYSQL_DB,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE student_attendance_records ADD UNIQUE INDEX uniq_student_att_new (department, semester_number, subject, attendance_date, student_id)")
        except:
            pass

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
                package VARCHAR(255) NOT NULL,
                status VARCHAR(50) DEFAULT 'Offered'
            )
        """)

        # If placements.status is missing in an existing DB, add it.
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'placements' AND COLUMN_NAME = 'status'
            """, (MYSQL_DB,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE placements ADD COLUMN status VARCHAR(50) DEFAULT 'Offered'")
        except:
            pass

        # Create faculty table (for department chatbot)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faculty (
                id INT AUTO_INCREMENT PRIMARY KEY,
                department VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                designation VARCHAR(255),
                qualification VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(50)
            )
        """)

        # Create department notices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS department_notices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                department VARCHAR(255) NOT NULL,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create notifications table (used to alert students, e.g. failed subjects)
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

        # Create student_sgpa_cgpa table (for SGPA/CGPA chatbot)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_sgpa_cgpa (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id VARCHAR(20) NOT NULL,
                department VARCHAR(255) NOT NULL,
                semester_number INT NOT NULL,
                sgpa DECIMAL(4,2),
                cgpa DECIMAL(4,2),
                UNIQUE KEY uniq_student_sem (student_id, department, semester_number)
            )
        """)

        # Create faculty_subjects mapping table (for "who teaches X?")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faculty_subjects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                department VARCHAR(255) NOT NULL,
                subject_name VARCHAR(255) NOT NULL,
                faculty_name VARCHAR(255) NOT NULL
            )
        """)


        # Add semester_number column to existing tables if not exists
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'attendance_records' AND COLUMN_NAME = 'semester_number'
            """, (MYSQL_DB,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE attendance_records ADD COLUMN semester_number INT AFTER department")
        except:
            pass

        try:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'timetable_entries' AND COLUMN_NAME = 'semester_number'
            """, (MYSQL_DB,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE timetable_entries ADD COLUMN semester_number INT AFTER department")
        except:
            pass

        try:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'exam_schedule' AND COLUMN_NAME = 'semester_number'
            """, (MYSQL_DB,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE exam_schedule ADD COLUMN semester_number INT AFTER department")
        except:
            pass

        # Create semesters table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS semesters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                semester_number INT NOT NULL UNIQUE,
                description VARCHAR(255)
            )
        """)

        # Create semester_subjects table (subjects per semester per department)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS semester_subjects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                department VARCHAR(255) NOT NULL,
                semester_number INT NOT NULL,
                subject_name VARCHAR(255) NOT NULL,
                subject_code VARCHAR(50),
                UNIQUE KEY unique_dept_sem_subj (department, semester_number, subject_name)
            )
        """)

        # Create student_results table (marks per student per subject)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id VARCHAR(20) NOT NULL,
                department VARCHAR(255) NOT NULL,
                semester_number INT NOT NULL,
                subject_name VARCHAR(255) NOT NULL,
                marks INT DEFAULT 0,
                max_marks INT DEFAULT 100,
                UNIQUE KEY unique_student_result (student_id, semester_number, subject_name)
            )
        """)

        conn.commit()
        print("Database tables created successfully!")

        # Seed sample data
        seed_data(cursor, conn)

    finally:
        conn.close()


def seed_data(cursor, conn) -> None:
    """Seed sample data for departments"""

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM attendance_records")
    if cursor.fetchone()[0] > 0:
        print("Data already exists, skipping seed...")
        return

    departments = ["Computer Science", "Electronics", "Mechanical", "Civil", "Electrical"]

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

    timetable = []
    for dept in departments:
        for idx, subj in enumerate(attendance_subjects[dept]):
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
        for subj_idx, subj in enumerate(attendance_subjects[dept]):
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

    # Seed Semesters (1-8 for typical MCA program)
    semesters = [(1, "First Semester"), (2, "Second Semester"), (3, "Third Semester"), (4, "Fourth Semester")]
    cursor.executemany(
        "INSERT INTO semesters (semester_number, description) VALUES (%s, %s)",
        semesters
    )

    # Seed semester-wise subjects per department
    semester_subjects_data = {
        "Computer Science": {
            1: [("CS101", "Programming in C"), ("CS102", "Data Structures"), ("CS103", "Discrete Mathematics"), ("CS104", "Computer Fundamentals")],
            2: [("CS201", "Object Oriented Programming"), ("CS202", "Operating Systems"), ("CS203", "Database Management"), ("CS204", "Software Engineering")],
            3: [("CS301", "Web Technologies"), ("CS302", "Computer Networks"), ("CS303", "Artificial Intelligence"), ("CS304", "Cloud Computing")],
            4: [("CS401", "Machine Learning"), ("CS402", "Cyber Security"), ("CS403", "Project Work"), ("CS404", "Seminar")]
        },
        "Electronics": {
            1: [("EC101", "Circuit Analysis"), ("EC102", "Digital Electronics"), ("EC103", "Physics"), ("EC104", "Mathematics")],
            2: [("EC201", "Signal Processing"), ("EC202", "Microprocessors"), ("EC203", "Communication Systems"), ("EC204", "Electronic Circuits")],
            3: [("EC301", "VLSI Design"), ("EC302", "Embedded Systems"), ("EC303", "Power Electronics"), ("EC304", "Control Systems")],
            4: [("EC401", "Instrumentation"), ("EC402", "Wireless Communication"), ("EC403", "Project Work"), ("EC404", "Seminar")]
        },
        "Mechanical": {
            1: [("ME101", "Engineering Graphics"), ("ME102", "Thermodynamics"), ("ME103", "Mathematics"), ("ME104", "Physics")],
            2: [("ME201", "Fluid Mechanics"), ("ME202", "Manufacturing Process"), ("ME203", "Machine Design"), ("ME204", "Strength of Materials")],
            3: [("ME301", "IC Engines"), ("ME302", "Heat Transfer"), ("ME303", "Robotics"), ("ME304", "Finite Element Analysis")],
            4: [("ME401", "Automobile Engineering"), ("ME402", "CAD/CAM"), ("ME403", "Project Work"), ("ME404", "Seminar")]
        },
        "Civil": {
            1: [("CV101", "Surveying"), ("CV102", "Structural Analysis"), ("CV103", "Mathematics"), ("CV104", "Physics")],
            2: [("CV201", "Concrete Technology"), ("CV202", "Geotechnical Engineering"), ("CV203", "Hydrology"), ("CV204", "Environmental Engineering")],
            3: [("CV301", "Highway Engineering"), ("CV302", "Steel Design"), ("CV303", "Foundation Engineering"), ("CV304", "Building Materials")],
            4: [("CV401", "Construction Management"), ("CV402", "Town Planning"), ("CV403", "Project Work"), ("CV404", "Seminar")]
        },
        "Electrical": {
            1: [("EE101", "Circuit Theory"), ("EE102", "Electrical Machines"), ("EE103", "Mathematics"), ("EE104", "Physics")],
            2: [("EE201", "Power Systems"), ("EE202", "Control Systems"), ("EE203", "Power Electronics"), ("EE204", "Measurements")],
            3: [("EE301", "High Voltage Engineering"), ("EE302", "Renewable Energy"), ("EE303", "Digital Signal Processing"), ("EE304", "Utilization of Electrical Energy")],
            4: [("EE401", "Smart Grid"), ("EE402", "Electric Vehicles"), ("EE403", "Project Work"), ("EE404", "Seminar")]
        }
    }

    semester_subjects = []
    for dept in departments:
        for sem_num, subjects in semester_subjects_data[dept].items():
            for code, name in subjects:
                semester_subjects.append((dept, sem_num, name, code))
    cursor.executemany(
        "INSERT INTO semester_subjects (department, semester_number, subject_name, subject_code) VALUES (%s, %s, %s, %s)",
        semester_subjects
    )

    conn.commit()
    print("Seeded 50 attendance, 50 timetable, 50 exam, 50 placement, semesters and semester-wise subjects!")


if __name__ == "__main__":
    init_db()
    print("Database initialized")
