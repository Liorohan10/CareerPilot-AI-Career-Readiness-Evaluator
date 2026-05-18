from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.services.pdf_parser import extract_text_from_pdf
from backend.workflows.recruitment_workflow import run_recruitment_workflow

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
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Groq LangGraph workflow failed. Please retry.") from exc
