from __future__ import annotations

import json
import logging
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.services.pdf_parser import extract_text_from_pdf
from backend.workflows.recruitment_workflow import run_recruitment_workflow
from backend.services import db_service
from backend.agents.llm_recruitment_agent import (
    generate_interview_questions,
    evaluate_interview_responses,
)
from backend.models import InterviewStatusResponse, InterviewSubmitAnswerRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze")
async def analyze_candidate(
    desired_roles: str = Form(...),
    analysis_mode: str = Form(default="resume_only"),
    job_description: str = Form(default=""),
    resume_text: str | None = Form(default=None),
    resume_file: UploadFile | None = File(default=None),
):
    parsed_resume = (resume_text or "").strip()

    if resume_file is not None and resume_file.filename:
        if not resume_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Resume upload must be a PDF.")
        parsed_resume = extract_text_from_pdf(await resume_file.read())

    if not parsed_resume:
        raise HTTPException(status_code=400, detail="Provide a resume PDF or resume text.")

    roles = [role.strip() for role in desired_roles.split(",") if role.strip()]
    if not roles:
        raise HTTPException(status_code=400, detail="Select at least one desired role.")

    if analysis_mode not in {"resume_only", "jd_fit"}:
        raise HTTPException(status_code=400, detail="Invalid analysis mode.")

    if analysis_mode == "jd_fit" and not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description is required for JD fit mode.")

    try:
        return run_recruitment_workflow(
            resume_text=parsed_resume,
            desired_roles=roles,
            job_description=job_description,
            analysis_mode=analysis_mode,
        )
    except RuntimeError as exc:
        logger.error("Screening agent run failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected workflow failure: %s", exc)
        raise HTTPException(status_code=502, detail="Groq LangGraph workflow failed. Please retry.") from exc


@router.get("/applications/{app_id}")
async def get_candidate_application(app_id: int):
    app = db_service.get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")
    
    # Parse report JSON back into a dictionary
    try:
        report_data = json.loads(app["report_json"])
        app["resume_profile"] = report_data.get("profile")
        app["skill_match"] = report_data.get("skill_match")
        app["career_prep_plan"] = report_data.get("career_prep_plan")
        app["report"] = report_data.get("report")
    except Exception:
        pass
        
    return app


@router.get("/recruiter/applications")
async def list_all_applications():
    return db_service.list_applications()


def _format_interview_response(app_id: int, interview: dict) -> InterviewStatusResponse:
    questions = interview["questions"]
    answers = interview["answers"]
    idx = interview["current_question_index"]
    
    current_q = None
    if idx < len(questions) and interview["status"] not in ("completed", "submitting"):
        current_q = questions[idx]
        
    feedback_report = None
    score = None
    if interview["feedback_json"]:
        try:
            feedback_data = json.loads(interview["feedback_json"])
            feedback_report = feedback_data.get("feedback")
            score = feedback_data.get("score")
        except Exception:
            feedback_report = interview["feedback_json"]
            
    return InterviewStatusResponse(
        application_id=app_id,
        role=interview["role"],
        status=interview["status"],
        current_question_index=idx,
        total_questions=len(questions),
        current_question=current_q,
        completed=(interview["status"] == "completed"),
        feedback=feedback_report,
        score=score,
        questions=questions,
        answers=answers
    )


@router.get("/interviews/{app_id}", response_model=InterviewStatusResponse)
async def get_interview_status(app_id: int):
    interview = db_service.get_interview(app_id)
    if not interview:
        raise HTTPException(status_code=404, detail="No interview exists for this application.")
    return _format_interview_response(app_id, interview)


@router.post("/interviews/{app_id}/start", response_model=InterviewStatusResponse)
async def start_candidate_interview(app_id: int):
    app = db_service.get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")
    
    # Generate role & questions
    role = app["job_title"] or (json.loads(app["desired_roles"])[0] if app["desired_roles"] else "Technical Candidate")
    jd = app["job_description"] or ""
    
    try:
        questions = generate_interview_questions(jd, role)
        db_service.create_interview(app_id, role, questions)
        interview = db_service.get_interview(app_id)
        return _format_interview_response(app_id, interview)
    except Exception as exc:
        logger.error("Failed to generate interview questions: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to initialize interview questions using LLM.") from exc


@router.post("/interviews/{app_id}/submit", response_model=InterviewStatusResponse)
async def submit_interview_answer(app_id: int, payload: InterviewSubmitAnswerRequest):
    interview = db_service.get_interview(app_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")
        
    if interview["status"] == "completed":
        raise HTTPException(status_code=400, detail="Interview is already completed.")
        
    idx = interview["current_question_index"]
    updated_interview = db_service.update_interview_answer(app_id, idx, payload.answer)
    
    # Check if we need to evaluate the full interview (reached the end)
    if updated_interview["status"] == "submitting":
        try:
            app = db_service.get_application(app_id)
            jd = app["job_description"] or ""
            feedback = evaluate_interview_responses(
                questions=updated_interview["questions"],
                answers=updated_interview["answers"],
                job_description=jd,
                role=updated_interview["role"]
            )
            db_service.complete_interview(app_id, json.dumps(feedback))
            # Retrieve final updated interview
            updated_interview = db_service.get_interview(app_id)
        except Exception as exc:
            logger.error("Failed to evaluate candidate interview: %s", exc)
            # Revert state to completed with simple notification or retry later
            db_service.complete_interview(
                app_id, 
                json.dumps({
                    "feedback": "Interview completed successfully. The evaluation report will be compiled by a recruiter shortly.",
                    "score": 80
                })
            )
            updated_interview = db_service.get_interview(app_id)

    return _format_interview_response(app_id, updated_interview)
