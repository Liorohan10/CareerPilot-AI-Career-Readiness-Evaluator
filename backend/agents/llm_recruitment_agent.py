from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TypeVar

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from backend.models import CareerPrepPlan, ResumeProfile, SkillMatch
from backend.services.env_loader import load_local_env

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
T = TypeVar("T")


def invoke_groq_with_retries(action: Callable[[], T]) -> T:
    delays = [1.0, 2.0, 4.0]
    for attempt, delay in enumerate(delays):
        try:
            return action()
        except Exception as exc:
            message = str(exc).lower()
            is_rate_limit = "rate_limit" in message or "rate limit" in message or "429" in message
            if not is_rate_limit:
                raise
            if attempt == len(delays) - 1:
                raise
            time.sleep(delay)
    return action()


def get_groq_llm(temperature: float = 0.1) -> ChatGroq:
    load_local_env()
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is required to run the LangGraph AI workflow.")

    return ChatGroq(
        model=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        temperature=temperature,
        max_retries=2,
    )


def analyze_resume_with_llm(resume_text: str) -> ResumeProfile:
    parser = PydanticOutputParser(pydantic_object=ResumeProfile)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a resume screening agent. Extract structured information from the resume. "
                "Do not invent skills, education, certifications, projects, or years of experience. "
                "If something is missing, return an empty list or 0. Return valid JSON only.",
            ),
            (
                "human",
                """
Analyze this resume text and return structured resume data.

Resume:
{resume_text}

{format_instructions}
""",
            ),
        ]
    )
    chain = prompt | get_groq_llm() | parser
    return invoke_groq_with_retries(
        lambda: chain.invoke(
            {
                "resume_text": resume_text,
                "format_instructions": parser.get_format_instructions(),
            }
        )
    )


def match_skills_with_llm(
    profile: ResumeProfile,
    desired_roles: list[str],
    analysis_mode: str,
    job_description: str = "",
) -> SkillMatch:
    parser = PydanticOutputParser(pydantic_object=SkillMatch)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a skill matching agent. Compare the candidate profile against the target roles "
                "and, when provided, the job description. Return a realistic match score from 0 to 100, "
                "required skills, skills the candidate already has, and missing skills. "
                "Use only evidence from the resume profile for strong areas. Return valid JSON only.",
            ),
            (
                "human",
                """
Analysis mode: {analysis_mode}
Desired roles: {desired_roles}
Job description: {job_description}

Candidate resume profile:
{profile}

Return the candidate-role match as structured data.

{format_instructions}
""",
            ),
        ]
    )
    chain = prompt | get_groq_llm() | parser
    return invoke_groq_with_retries(
        lambda: chain.invoke(
            {
                "analysis_mode": analysis_mode,
                "desired_roles": ", ".join(desired_roles),
                "job_description": job_description or "Not provided",
                "profile": profile.model_dump(),
                "format_instructions": parser.get_format_instructions(),
            }
        )
    )


def build_career_prep_plan_with_llm(
    profile: ResumeProfile,
    skill_match: SkillMatch,
    target_roles: list[str],
    analysis_mode: str,
    job_description: str = "",
) -> CareerPrepPlan:
    parser = PydanticOutputParser(pydantic_object=CareerPrepPlan)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an expert career coach and technical interview mentor. "
                "Return only valid JSON matching the requested schema. "
                "Be specific, practical, honest, and candidate-friendly.",
            ),
            (
                "human",
                """
Analyze this candidate for career readiness.

Analysis mode: {analysis_mode}
Target roles: {target_roles}
Job description, if supplied: {job_description}

Resume profile:
{profile}

Skill match:
{skill_match}

Create:
- SWOT analysis with at least 2 items in each SWOT category
- practical roadmap with at least 3 phases and at least 2 actions per phase
- at least 5 probable interview questions
- at least 4 interview preparation steps

Set analysis_source to "groq_llm".
Use role_fit_score from the skill match score.

{format_instructions}
""",
            ),
        ]
    )
    chain = prompt | get_groq_llm(temperature=0.2) | parser
    plan = invoke_groq_with_retries(
        lambda: chain.invoke(
            {
                "analysis_mode": analysis_mode,
                "target_roles": ", ".join(target_roles),
                "job_description": job_description or "Not provided",
                "profile": profile.model_dump(),
                "skill_match": skill_match.model_dump(),
                "format_instructions": parser.get_format_instructions(),
            }
        )
    )
    plan.analysis_mode = analysis_mode
    plan.analysis_source = "groq_llm"
    plan.target_roles = target_roles
    plan.role_fit_score = skill_match.match_score
    return plan
