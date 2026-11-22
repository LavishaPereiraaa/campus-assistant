import os
import mysql.connector
from mysql.connector import Error

def _load_env_file(env_path: str) -> None:
    """Load environment variables from .env file"""
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
    """Ensure environment variables are loaded"""
    if any(os.getenv(k) for k in ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB")):
        return
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _load_env_file(os.path.join(base_dir, ".env.local"))
    _load_env_file(os.path.join(base_dir, ".env"))

def _get_env(name: str, default: str | None = None) -> str:
    """Get environment variable"""
    _ensure_env_loaded()
    val = os.getenv(name, default)
    if val is None:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            f"Create a .env.local/.env with MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB."
        )
    return val

def _run_migrations():
    """Run database migrations to add missing columns"""
    try:
        conn = mysql.connector.connect(
            host=_get_env("MYSQL_HOST"),
            user=_get_env("MYSQL_USER"),
            password=_get_env("MYSQL_PASSWORD"),
            database=_get_env("MYSQL_DB"),
            autocommit=False
        )
        cursor = conn.cursor()
        db_name = _get_env("MYSQL_DB")

        # Add semester_number and subject columns to student_attendance_records
        try:
            cursor.execute(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'student_attendance_records' AND COLUMN_NAME = 'semester_number'
            """, (db_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE student_attendance_records ADD COLUMN semester_number INT AFTER department")
        except:
            pass
        try:
            cursor.execute(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'student_attendance_records' AND COLUMN_NAME = 'subject'
            """, (db_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE student_attendance_records ADD COLUMN subject VARCHAR(255) AFTER semester_number")
        except:
            pass

        # Add semester_number to timetable_entries
        try:
            cursor.execute(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'timetable_entries' AND COLUMN_NAME = 'semester_number'
            """, (db_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE timetable_entries ADD COLUMN semester_number INT AFTER department")
        except:
            pass

        # Add semester_number to exam_schedule
        try:
            cursor.execute(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'exam_schedule' AND COLUMN_NAME = 'semester_number'
            """, (db_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE exam_schedule ADD COLUMN semester_number INT AFTER department")
        except:
            pass

        # Add semester_number to attendance_records
        try:
            cursor.execute(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'attendance_records' AND COLUMN_NAME = 'semester_number'
            """, (db_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE attendance_records ADD COLUMN semester_number INT AFTER department")
        except:
            pass

        # Create notifications table if it doesn't exist (used to alert students, e.g. failed subjects)
        try:
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
        except:
            pass

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Migration error: {e}")

def connect_db():
    """Return a new MySQL database connection per request"""
    _run_migrations()
    return mysql.connector.connect(
        host=_get_env("MYSQL_HOST"),
        user=_get_env("MYSQL_USER"),
        password=_get_env("MYSQL_PASSWORD"),
        database=_get_env("MYSQL_DB"),
        autocommit=False
    )

def get_db_config():
    """Return database configuration dict"""
    _ensure_env_loaded()
    return {
        "host": _get_env("MYSQL_HOST"),
        "user": _get_env("MYSQL_USER"),
        "password": _get_env("MYSQL_PASSWORD"),
        "database": _get_env("MYSQL_DB")
    }