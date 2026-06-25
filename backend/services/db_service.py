from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join("database", "recruitment.db")


def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create candidates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            resume_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Create jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            desired_roles TEXT
        )
    """)

    # Create applications table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            job_id INTEGER,
            analysis_mode TEXT NOT NULL,
            fit_score INTEGER NOT NULL,
            report_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates (id),
            FOREIGN KEY (job_id) REFERENCES jobs (id)
        )
    """)

    # Create interviews table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL UNIQUE,
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            current_question_index INTEGER DEFAULT 0,
            questions_json TEXT NOT NULL,
            answers_json TEXT NOT NULL,
            feedback_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (application_id) REFERENCES applications (id)
        )
    """)

    conn.commit()
    conn.close()


def save_candidate(name: str, email: str | None, resume_text: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO candidates (name, email, resume_text, created_at) VALUES (?, ?, ?, ?)",
        (name, email or "", resume_text, created_at)
    )
    candidate_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return candidate_id


def save_job(title: str, description: str, desired_roles: list[str]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO jobs (title, description, desired_roles) VALUES (?, ?, ?)",
        (title, description, json.dumps(desired_roles))
    )
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id


def create_application(
    candidate_id: int,
    job_id: int | None,
    analysis_mode: str,
    fit_score: int,
    report_json: str,
    status: str
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO applications (candidate_id, job_id, analysis_mode, fit_score, report_json, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (candidate_id, job_id, analysis_mode, fit_score, report_json, status, created_at)
    )
    application_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return application_id


def get_application(app_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.id, a.candidate_id, a.job_id, a.analysis_mode, a.fit_score, a.report_json, a.status, a.created_at,
               c.name as candidate_name, c.email as candidate_email, c.resume_text,
               j.title as job_title, j.description as job_description, j.desired_roles
        FROM applications a
        JOIN candidates c ON a.candidate_id = c.id
        LEFT JOIN jobs j ON a.job_id = j.id
        WHERE a.id = ?
        """,
        (app_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def update_application_status(app_id: int, status: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE applications SET status = ? WHERE id = ?", (status, app_id))
    conn.commit()
    conn.close()


def list_applications() -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.id, a.candidate_id, a.job_id, a.analysis_mode, a.fit_score, a.status, a.created_at,
               c.name as candidate_name, c.email as candidate_email,
               j.title as job_title, j.desired_roles,
               i.status as interview_status, i.feedback_json
        FROM applications a
        JOIN candidates c ON a.candidate_id = c.id
        LEFT JOIN jobs j ON a.job_id = j.id
        LEFT JOIN interviews i ON a.id = i.application_id
        ORDER BY a.id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_interview(application_id: int, role: str, questions: list[str]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    # If an interview already exists, retrieve its ID, or update it
    cursor.execute("SELECT id FROM interviews WHERE application_id = ?", (application_id,))
    row = cursor.fetchone()
    if row:
        interview_id = row["id"]
        cursor.execute(
            """
            UPDATE interviews
            SET role = ?, status = 'scheduled', current_question_index = 0,
                questions_json = ?, answers_json = ?, feedback_json = NULL
            WHERE id = ?
            """,
            (role, json.dumps(questions), json.dumps([""] * len(questions)), interview_id)
        )
    else:
        cursor.execute(
            """
            INSERT INTO interviews (application_id, role, status, current_question_index, questions_json, answers_json, created_at)
            VALUES (?, ?, 'scheduled', 0, ?, ?, ?)
            """,
            (application_id, role, json.dumps(questions), json.dumps([""] * len(questions)), created_at)
        )
        interview_id = cursor.lastrowid
    
    # Also update application status
    cursor.execute(
        "UPDATE applications SET status = 'interview_scheduled' WHERE id = ?",
        (application_id,)
    )
    
    conn.commit()
    conn.close()
    return interview_id


def get_interview(app_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, application_id, role, status, current_question_index, questions_json, answers_json, feedback_json
        FROM interviews
        WHERE application_id = ?
        """,
        (app_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        data = dict(row)
        data["questions"] = json.loads(data["questions_json"])
        data["answers"] = json.loads(data["answers_json"])
        return data
    return None


def update_interview_answer(app_id: int, question_index: int, answer: str) -> dict | None:
    interview = get_interview(app_id)
    if not interview:
        return None

    answers = interview["answers"]
    if 0 <= question_index < len(answers):
        answers[question_index] = answer

    new_index = question_index + 1
    status = "ongoing"
    if new_index >= len(interview["questions"]):
        status = "submitting" # will be evaluated

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE interviews
        SET answers_json = ?, current_question_index = ?, status = ?
        WHERE application_id = ?
        """,
        (json.dumps(answers), new_index, status, app_id)
    )
    
    # Also update application status
    cursor.execute(
        "UPDATE applications SET status = ? WHERE id = ?",
        (status, app_id)
    )
    
    conn.commit()
    conn.close()
    return get_interview(app_id)


def complete_interview(app_id: int, feedback_json: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE interviews
        SET status = 'completed', feedback_json = ?
        WHERE application_id = ?
        """,
        (feedback_json, app_id)
    )
    
    cursor.execute(
        "UPDATE applications SET status = 'interview_completed' WHERE id = ?",
        (app_id,)
    )
    conn.commit()
    conn.close()
