from __future__ import annotations

import json
from typing import TypedDict

from backend.agents.llm_recruitment_agent import (
    analyze_resume_with_llm,
    build_career_prep_plan_with_llm,
    match_skills_with_llm,
)
from backend.agents.report_generation_agent import generate_report
from backend.models import CareerPrepPlan, RecruitmentReport, ResumeProfile, SkillMatch
from backend.services.vector_service import get_semantic_overlaps
from backend.services.db_service import save_candidate, save_job, create_application


class RecruitmentState(TypedDict, total=False):
    resume_text: str
    desired_roles: list[str]
    job_description: str
    analysis_mode: str
    profile: ResumeProfile
    skill_match: SkillMatch
    prep_plan: CareerPrepPlan
    report: str


def parse_resume_node(state: RecruitmentState) -> dict[str, ResumeProfile]:
    return {"profile": analyze_resume_with_llm(state["resume_text"])}


def match_skills_node(state: RecruitmentState) -> dict[str, SkillMatch]:
    semantic_context = ""
    if state["analysis_mode"] == "jd_fit" and state.get("job_description"):
        semantic_context = get_semantic_overlaps(
            state["resume_text"], 
            state["job_description"]
        )

    return {
        "skill_match": match_skills_with_llm(
            profile=state["profile"],
            desired_roles=state["desired_roles"],
            analysis_mode=state["analysis_mode"],
            job_description=state.get("job_description", ""),
            semantic_context=semantic_context,
        )
    }


def career_advisor_node(state: RecruitmentState) -> dict[str, CareerPrepPlan]:
    return {
        "prep_plan": build_career_prep_plan_with_llm(
            profile=state["profile"],
            skill_match=state["skill_match"],
            target_roles=state["desired_roles"],
            analysis_mode=state["analysis_mode"],
            job_description=state.get("job_description", ""),
        )
    }


def report_node(state: RecruitmentState) -> dict[str, str]:
    return {
        "report": generate_report(
            profile=state["profile"],
            skill_match=state["skill_match"],
            prep_plan=state["prep_plan"],
        )
    }


def _run_langgraph_workflow(initial_state: RecruitmentState) -> RecruitmentState:
    from langgraph.graph import END, StateGraph

    graph = StateGraph(RecruitmentState)
    graph.add_node("parse_resume", parse_resume_node)
    graph.add_node("match_skills", match_skills_node)
    graph.add_node("career_advisor", career_advisor_node)
    graph.add_node("generate_report", report_node)
    graph.set_entry_point("parse_resume")
    graph.add_edge("parse_resume", "match_skills")
    graph.add_edge("match_skills", "career_advisor")
    graph.add_edge("career_advisor", "generate_report")
    graph.add_edge("generate_report", END)

    compiled = graph.compile()
    return compiled.invoke(initial_state)


def run_recruitment_workflow(
    resume_text: str,
    desired_roles: list[str],
    job_description: str = "",
    analysis_mode: str = "resume_only",
) -> RecruitmentReport:
    final_state = _run_langgraph_workflow(
        {
            "resume_text": resume_text,
            "desired_roles": desired_roles,
            "job_description": job_description,
            "analysis_mode": analysis_mode,
        }
    )

    # 1. Extract details and save to SQLite DB
    profile = final_state["profile"]
    skill_match = final_state["skill_match"]
    prep_plan = final_state["prep_plan"]
    report = final_state["report"]

    candidate_name = profile.candidate_name or "Candidate"
    candidate_email = profile.candidate_email or ""
    candidate_id = save_candidate(candidate_name, candidate_email, resume_text)

    # 2. Save job if JD fit mode
    job_id = None
    if analysis_mode == "jd_fit":
        job_title = desired_roles[0] if desired_roles else "Unknown Role"
        job_id = save_job(job_title, job_description, desired_roles)

    # 3. Create application record
    report_data = {
        "profile": profile.model_dump(),
        "skill_match": skill_match.model_dump(),
        "career_prep_plan": prep_plan.model_dump(),
        "report": report
    }
    report_json = json.dumps(report_data)
    
    fit_score = skill_match.match_score
    status = "proceeded_to_interview" if fit_score >= 70 else "analyzed"

    application_id = create_application(
        candidate_id=candidate_id,
        job_id=job_id,
        analysis_mode=analysis_mode,
        fit_score=fit_score,
        report_json=report_json,
        status=status
    )

    return RecruitmentReport(
        application_id=application_id,
        resume_profile=profile,
        skill_match=skill_match,
        career_prep_plan=prep_plan,
        report=report,
    )
