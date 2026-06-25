from __future__ import annotations

import os
import shutil
import pytest
import sqlite3

from backend.services import db_service
from backend.services import vector_service

# Test DB setup and teardown
TEST_DB_PATH = os.path.join("database", "recruitment_test.db")

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    # Override database path to use a test DB file
    monkeypatch.setattr(db_service, "DB_PATH", TEST_DB_PATH)
    
    # Initialize clean DB
    db_service.init_db()
    
    yield
    
    # Remove test DB file after tests run
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


def test_sqlite_db_candidate_operations():
    # Save a candidate
    candidate_id = db_service.save_candidate("Jane Doe", "jane@example.com", "Resume content...")
    assert candidate_id == 1

    # Save a job
    job_id = db_service.save_job("DevOps Engineer", "Manage Kubernetes", ["DevOps Engineer"])
    assert job_id == 1

    # Create application
    app_id = db_service.create_application(
        candidate_id=candidate_id,
        job_id=job_id,
        analysis_mode="jd_fit",
        fit_score=85,
        report_json='{"summary": "great"}',
        status="proceeded_to_interview"
    )
    assert app_id == 1

    # Retrieve application
    app = db_service.get_application(app_id)
    assert app is not None
    assert app["candidate_name"] == "Jane Doe"
    assert app["job_title"] == "DevOps Engineer"
    assert app["fit_score"] == 85
    assert app["status"] == "proceeded_to_interview"


def test_sqlite_db_interview_operations():
    # Insert candidate, job, application
    candidate_id = db_service.save_candidate("Alice Smith", "alice@example.com", "Resume text")
    job_id = db_service.save_job("Frontend Developer", "Build React UIs", ["Frontend Developer"])
    app_id = db_service.create_application(
        candidate_id=candidate_id,
        job_id=job_id,
        analysis_mode="jd_fit",
        fit_score=75,
        report_json="{}",
        status="proceeded_to_interview"
    )

    # Create interview
    questions = ["Q1: Tell me about yourself.", "Q2: React state vs props?"]
    interview_id = db_service.create_interview(app_id, "Frontend Developer", questions)
    assert interview_id == 1

    # Retrieve interview
    int_obj = db_service.get_interview(app_id)
    assert int_obj is not None
    assert int_obj["role"] == "Frontend Developer"
    assert int_obj["status"] == "scheduled"
    assert int_obj["questions"] == questions
    assert int_obj["current_question_index"] == 0

    # Submit an answer
    updated = db_service.update_interview_answer(app_id, 0, "I am Alice.")
    assert updated["current_question_index"] == 1
    assert updated["answers"][0] == "I am Alice."
    assert updated["status"] == "ongoing"

    # Submit second answer to finish
    updated = db_service.update_interview_answer(app_id, 1, "State is local, props are passed down.")
    assert updated["current_question_index"] == 2
    assert updated["answers"][1] == "State is local, props are passed down."
    assert updated["status"] == "submitting"

    # Complete interview with feedback
    db_service.complete_interview(app_id, '{"feedback": "excellent candidate", "score": 90}')
    
    # Verify final completed state
    final = db_service.get_interview(app_id)
    assert final["status"] == "completed"
    assert "excellent candidate" in final["feedback_json"]


def test_text_chunking():
    text = "Paragraph 1 is here.\n\nParagraph 2 is here. It is longer than paragraph one."
    chunks = vector_service.chunk_text(text, chunk_size=30, chunk_overlap=5)
    assert len(chunks) >= 2


def test_vector_semantic_matching():
    resume = "Candidate with 5 years experience building deep learning models using Python and PyTorch."
    jd = "Seeking a machine learning engineer proficient in Python and deep learning frameworks."
    
    overlaps = vector_service.get_semantic_overlaps(resume, jd, top_k=2)
    assert "Semantic" in overlaps or "vector-similarity" in overlaps
    # Verify overlaps are not blank and show matches
    assert len(overlaps) > 0
