import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "events.db"))

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL,
            video_filename TEXT,
            tracker_id INTEGER,
            visitor_name TEXT DEFAULT 'Gato',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE visits ADD COLUMN visitor_name TEXT DEFAULT 'Gato'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def record_visit(start_time: str, end_time: str, duration_seconds: int, video_filename: Optional[str] = None, tracker_id: Optional[int] = None, visitor_name: str = "Gato") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO visits (start_time, end_time, duration_seconds, video_filename, tracker_id, visitor_name)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (start_time, end_time, duration_seconds, video_filename, tracker_id, visitor_name))
    visit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return visit_id

def get_visits(filter_range: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM visits"
    params = []
    
    if filter_range == "today":
        today_str = datetime.now().strftime("%Y-%m-%d")
        query += " WHERE start_time LIKE ?"
        params.append(f"{today_str}%")
    elif filter_range == "yesterday":
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        query += " WHERE start_time LIKE ?"
        params.append(f"{yesterday_str}%")
    elif filter_range == "week":
        week_ago_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        query += " WHERE start_time >= ?"
        params.append(week_ago_str)
        
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    visits = [dict(row) for row in rows]
    conn.close()
    return visits

def delete_visit(visit_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM visits WHERE id = ?", (visit_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_visits_breakdown(filter_range: Optional[str] = "today") -> Dict[str, int]:
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT visitor_name, COUNT(*) as count FROM visits"
    params = []
    if filter_range == "today":
        today_str = datetime.now().strftime("%Y-%m-%d")
        query += " WHERE start_time LIKE ?"
        params.append(f"{today_str}%")
    elif filter_range == "yesterday":
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        query += " WHERE start_time LIKE ?"
        params.append(f"{yesterday_str}%")
    elif filter_range == "week":
        week_ago_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        query += " WHERE start_time >= ?"
        params.append(week_ago_str)

    query += " GROUP BY visitor_name"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    breakdown = {row["visitor_name"]: row["count"] for row in rows}
    conn.close()
    return breakdown

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
