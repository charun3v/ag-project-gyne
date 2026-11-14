"""
Recent Patients Tracking Engine.
Tracks the most recent patient records opened by each user for a personalized dashboard worklist.
Ensures the main patient dashboard displays the 15 most recent patients accessed by the active user.
"""

from django.db import connection
from django.utils import timezone


def ensure_recent_patient_table():
    """Idempotently ensures tblUserRecentPatients table exists in the database."""
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tblUserRecentPatients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
                MR_No VARCHAR(64) NOT NULL REFERENCES tblPtDetails(MR_No) ON DELETE CASCADE,
                last_accessed DATETIME NOT NULL,
                UNIQUE(user_id, MR_No)
            )
        """)


def record_patient_opened(user, mr_no):
    """
    Records or updates the timestamp when an authenticated user opens/accesses a patient record.
    Safe against non-existent patients, unauthenticated users, or database locks.
    """
    if not user or not getattr(user, 'is_authenticated', False) or not mr_no:
        return

    mr_str = str(mr_no).strip()
    if not mr_str:
        return

    try:
        ensure_recent_patient_table()
        now_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        with connection.cursor() as cursor:
            # SQLite 3.24+ atomic upsert
            cursor.execute("""
                INSERT INTO tblUserRecentPatients (user_id, MR_No, last_accessed)
                VALUES (%s, %s, %s)
                ON CONFLICT(user_id, MR_No) DO UPDATE SET last_accessed = excluded.last_accessed
            """, [user.id, mr_str, now_str])
    except Exception:
        # Fallback or silent continuation
        pass


def get_user_recent_mr_nos(user, limit=15):
    """
    Returns an ordered list of MR numbers for the most recent 15 patients opened by the specified user.
    If the user has opened fewer than 15 patients (e.g. new user or fresh session), backfills with
    the most recently registered non-deleted patients up to limit=15.
    """
    ensure_recent_patient_table()
    mr_nos = []

    if user and getattr(user, 'is_authenticated', False):
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT r.MR_No
                    FROM tblUserRecentPatients r
                    JOIN tblPtDetails p ON r.MR_No = p.MR_No
                    WHERE r.user_id = %s AND p.Soft_Deleted = 0
                    ORDER BY r.last_accessed DESC
                    LIMIT %s
                """, [user.id, limit])
                rows = cursor.fetchall()
                mr_nos = [r[0] for r in rows]
        except Exception:
            mr_nos = []

    # If user has accessed fewer than limit patients, backfill with most recent registered patients
    if len(mr_nos) < limit:
        needed = limit - len(mr_nos)
        try:
            with connection.cursor() as cursor:
                if mr_nos:
                    placeholders = ','.join(['%s'] * len(mr_nos))
                    sql = f"""
                        SELECT MR_No FROM tblPtDetails
                        WHERE Soft_Deleted = 0 AND MR_No NOT IN ({placeholders})
                        ORDER BY Date_of_registration DESC, EnteredOn DESC
                        LIMIT %s
                    """
                    params = list(mr_nos) + [needed]
                else:
                    sql = """
                        SELECT MR_No FROM tblPtDetails
                        WHERE Soft_Deleted = 0
                        ORDER BY Date_of_registration DESC, EnteredOn DESC
                        LIMIT %s
                    """
                    params = [needed]
                cursor.execute(sql, params)
                fallback_rows = cursor.fetchall()
                mr_nos.extend([r[0] for r in fallback_rows])
        except Exception:
            pass

    return mr_nos[:limit]


class RecentPatientMiddleware:
    """
    Django middleware that intercepts any request where `mr_no` is present in view kwargs
    and automatically records the patient as opened by the current user.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if getattr(request, 'user', None) and request.user.is_authenticated:
            mr_no = view_kwargs.get('mr_no')
            if mr_no:
                record_patient_opened(request.user, mr_no)
        return None
