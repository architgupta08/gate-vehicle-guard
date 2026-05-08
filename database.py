"""
College Gate Monitor - Database Layer
SQLite-based storage for users, vehicles, and logs
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager
from werkzeug.security import generate_password_hash


class Database:
    def __init__(self, db_path='college_gate.db'):
        self.db_path = db_path
        self.init_db()
        self._seed_admin()

    @contextmanager
    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ─────────────────────────────────────────────
    #  Schema
    # ─────────────────────────────────────────────
    def init_db(self):
        with self.get_conn() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    email       TEXT    UNIQUE NOT NULL,
                    password    TEXT    NOT NULL,
                    role        TEXT    DEFAULT 'student',
                    student_id  TEXT,
                    phone       TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS vehicles (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    plate_number    TEXT    UNIQUE NOT NULL,
                    vehicle_type    TEXT    DEFAULT 'car',
                    make            TEXT,
                    model_name      TEXT,
                    color           TEXT,
                    description     TEXT,
                    registered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS logs (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_number TEXT    NOT NULL,
                    vehicle_id   INTEGER REFERENCES vehicles(id) ON DELETE SET NULL,
                    log_type     TEXT    NOT NULL CHECK(log_type IN ('entry','exit')),
                    timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confidence   REAL    DEFAULT 100.0,
                    notes        TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_logs_plate    ON logs(plate_number);
                CREATE INDEX IF NOT EXISTS idx_logs_ts       ON logs(timestamp);
                CREATE INDEX IF NOT EXISTS idx_vehicles_plate ON vehicles(plate_number);
            ''')

    def _seed_admin(self):
        with self.get_conn() as conn:
            exists = conn.execute(
                "SELECT id FROM users WHERE email='admin@college.edu'"
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO users(name,email,password,role,student_id) VALUES(?,?,?,?,?)",
                    ('Admin', 'admin@college.edu',
                     generate_password_hash('admin123'), 'admin', 'ADMIN001')
                )

    # ─────────────────────────────────────────────
    #  Users
    # ─────────────────────────────────────────────
    def get_user_by_email(self, email):
        with self.get_conn() as conn:
            row = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id):
        with self.get_conn() as conn:
            row = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            return dict(row) if row else None

    def create_user(self, name, email, password, role='student',
                    student_id='', phone=''):
        with self.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users(name,email,password,role,student_id,phone) VALUES(?,?,?,?,?,?)",
                (name, email, password, role, student_id, phone)
            )
            return cur.lastrowid

    def get_all_users(self):
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT id,name,email,role,student_id,phone,created_at FROM users ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────────
    #  Vehicles
    # ─────────────────────────────────────────────
    def add_vehicle(self, user_id, plate_number, vehicle_type,
                    make='', model_name='', color='', description=''):
        with self.get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO vehicles(user_id,plate_number,vehicle_type,make,model_name,color,description)
                   VALUES(?,?,?,?,?,?,?)""",
                (user_id, plate_number, vehicle_type, make, model_name, color, description)
            )
            return cur.lastrowid

    def get_vehicle_by_plate(self, plate):
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT v.*,u.name as owner_name,u.email as owner_email,
                          u.student_id as owner_student_id
                   FROM vehicles v LEFT JOIN users u ON v.user_id=u.id
                   WHERE v.plate_number=?""", (plate,)
            ).fetchone()
            return dict(row) if row else None

    def get_user_vehicles(self, user_id):
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM vehicles WHERE user_id=? ORDER BY registered_at DESC",
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_vehicles(self):
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT v.*,u.name as owner_name,u.email as owner_email,
                          u.student_id as owner_student_id
                   FROM vehicles v LEFT JOIN users u ON v.user_id=u.id
                   ORDER BY v.registered_at DESC"""
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_vehicle(self, vehicle_id, user_id=None):
        with self.get_conn() as conn:
            if user_id:
                conn.execute(
                    "DELETE FROM vehicles WHERE id=? AND user_id=?",
                    (vehicle_id, user_id)
                )
            else:
                conn.execute("DELETE FROM vehicles WHERE id=?", (vehicle_id,))

    # ─────────────────────────────────────────────
    #  Logs
    # ─────────────────────────────────────────────
    def is_vehicle_inside(self, plate):
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT log_type FROM logs WHERE plate_number=? ORDER BY timestamp DESC LIMIT 1",
                (plate,)
            ).fetchone()
            return bool(row and row['log_type'] == 'entry')

    def log_entry(self, plate, vehicle_id=None, confidence=100.0, notes=''):
        with self.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO logs(plate_number,vehicle_id,log_type,confidence,notes) VALUES(?,?,'entry',?,?)",
                (plate, vehicle_id, confidence, notes)
            )
            return cur.lastrowid

    def log_exit(self, plate, confidence=100.0, notes=''):
        with self.get_conn() as conn:
            v = conn.execute(
                "SELECT id FROM vehicles WHERE plate_number=?", (plate,)
            ).fetchone()
            vid = v['id'] if v else None
            cur = conn.execute(
                "INSERT INTO logs(plate_number,vehicle_id,log_type,confidence,notes) VALUES(?,?,'exit',?,?)",
                (plate, vid, confidence, notes)
            )
            return cur.lastrowid

    def get_all_logs(self, page=1, per_page=20, search='', date_filter='', log_type=''):
        with self.get_conn() as conn:
            offset = (page - 1) * per_page
            conditions, params = [], []

            if search:
                conditions.append('(l.plate_number LIKE ? OR u.name LIKE ? OR u.student_id LIKE ?)')
                params += [f'%{search}%', f'%{search}%', f'%{search}%']
            if date_filter:
                conditions.append('DATE(l.timestamp)=?')
                params.append(date_filter)
            if log_type:
                conditions.append('l.log_type=?')
                params.append(log_type)

            where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

            rows = conn.execute(f'''
                SELECT l.*,
                       v.vehicle_type,v.make,v.model_name,v.color,
                       u.name as owner_name,u.student_id as owner_student_id
                FROM logs l
                LEFT JOIN vehicles v ON l.vehicle_id=v.id
                LEFT JOIN users u ON v.user_id=u.id
                {where}
                ORDER BY l.timestamp DESC
                LIMIT ? OFFSET ?
            ''', params + [per_page, offset]).fetchall()

            total = conn.execute(f'''
                SELECT COUNT(*) FROM logs l
                LEFT JOIN vehicles v ON l.vehicle_id=v.id
                LEFT JOIN users u ON v.user_id=u.id
                {where}
            ''', params).fetchone()[0]

            return [dict(r) for r in rows], total

    def get_user_logs(self, user_id, page=1, per_page=20):
        with self.get_conn() as conn:
            offset = (page - 1) * per_page
            rows = conn.execute('''
                SELECT l.*,v.vehicle_type,v.make,v.model_name,v.color
                FROM logs l
                JOIN vehicles v ON l.vehicle_id=v.id
                WHERE v.user_id=?
                ORDER BY l.timestamp DESC
                LIMIT ? OFFSET ?
            ''', (user_id, per_page, offset)).fetchall()

            total = conn.execute('''
                SELECT COUNT(*) FROM logs l
                JOIN vehicles v ON l.vehicle_id=v.id
                WHERE v.user_id=?
            ''', (user_id,)).fetchone()[0]

            return [dict(r) for r in rows], total

    def get_recent_logs(self, limit=20):
        with self.get_conn() as conn:
            rows = conn.execute('''
                SELECT l.*,
                       v.vehicle_type,v.make,v.model_name,v.color,
                       u.name as owner_name,u.student_id as owner_student_id
                FROM logs l
                LEFT JOIN vehicles v ON l.vehicle_id=v.id
                LEFT JOIN users u ON v.user_id=u.id
                ORDER BY l.timestamp DESC LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_vehicles_inside(self):
        with self.get_conn() as conn:
            rows = conn.execute('''
                WITH ranked AS (
                    SELECT l.*,
                           v.vehicle_type,v.make,v.model_name,v.color,
                           u.name as owner_name,u.student_id as owner_student_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY l.plate_number ORDER BY l.timestamp DESC
                           ) as rn
                    FROM logs l
                    LEFT JOIN vehicles v ON l.plate_number=v.plate_number
                    LEFT JOIN users u ON v.user_id=u.id
                )
                SELECT * FROM ranked WHERE rn=1 AND log_type='entry'
                ORDER BY timestamp DESC
            ''').fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────────
    #  Stats
    # ─────────────────────────────────────────────
    def get_stats(self):
        with self.get_conn() as conn:
            today = datetime.now().strftime('%Y-%m-%d')

            total_vehicles       = conn.execute('SELECT COUNT(*) FROM vehicles').fetchone()[0]
            registered_students  = conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
            entries_today        = conn.execute(
                "SELECT COUNT(*) FROM logs WHERE log_type='entry' AND DATE(timestamp)=?", (today,)
            ).fetchone()[0]
            exits_today          = conn.execute(
                "SELECT COUNT(*) FROM logs WHERE log_type='exit'  AND DATE(timestamp)=?", (today,)
            ).fetchone()[0]

            currently_inside = conn.execute('''
                SELECT COUNT(*) FROM (
                    SELECT log_type,
                           ROW_NUMBER() OVER (PARTITION BY plate_number ORDER BY timestamp DESC) rn
                    FROM logs
                ) WHERE rn=1 AND log_type='entry'
            ''').fetchone()[0]

            hourly = conn.execute('''
                SELECT strftime('%H', timestamp) as hour, log_type, COUNT(*) as count
                FROM logs WHERE DATE(timestamp)=?
                GROUP BY hour, log_type ORDER BY hour
            ''', (today,)).fetchall()

            week_trend = conn.execute('''
                SELECT DATE(timestamp) as date, log_type, COUNT(*) as count
                FROM logs
                WHERE timestamp >= date('now','-6 days')
                GROUP BY date, log_type ORDER BY date
            ''').fetchall()

            unregistered_today = conn.execute('''
                SELECT COUNT(*) FROM logs l
                WHERE DATE(l.timestamp)=? AND l.vehicle_id IS NULL
            ''', (today,)).fetchone()[0]

            return {
                'total_vehicles': total_vehicles,
                'registered_students': registered_students,
                'entries_today': entries_today,
                'exits_today': exits_today,
                'currently_inside': currently_inside,
                'unregistered_today': unregistered_today,
                'hourly': [dict(r) for r in hourly],
                'week_trend': [dict(r) for r in week_trend],
            }
