from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TypeVar

import httpx
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.models import CareerPrepPlan, ResumeProfile, SkillMatch
from backend.services.env_loader import load_local_env

T = TypeVar("T")


def invoke_llm_with_retries(action: Callable[[], T]) -> T:
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


def get_llm(temperature: float = 0.1) -> ChatOpenAI:
    load_local_env()
    api_key = os.getenv("GENAILAB_API_KEY")
    if not api_key:
        raise RuntimeError("GENAILAB_API_KEY is required to run the LangGraph AI workflow.")

    model = os.getenv("GENAILAB_MODEL", "azure_ai/genailab-maas-DeepSeek-V3-0324")

    # Enterprise proxy / SSL verification disable via custom client
    client = httpx.Client(verify=False)

    return ChatOpenAI(
        base_url="https://genailab.tcs.in",
        model=model,
        api_key=api_key,
        http_client=client,
        temperature=temperature,
    )




def analyze_resume_with_llm(resume_text: str) -> ResumeProfile:
    parser = PydanticOutputParser(pydantic_object=ResumeProfile)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a resume screening agent. Extract structured information from the resume, "
                "including the candidate's name and contact email. "
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
    chain = prompt | get_llm() | parser
    return invoke_llm_with_retries(
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
    semantic_context: str = "",
) -> SkillMatch:
    parser = PydanticOutputParser(pydantic_object=SkillMatch)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an advanced skill matching agent. Compare the candidate profile against the target roles "
                "and, when provided, the job description. Return a realistic match score from 0 to 100, "
                "required skills, skills the candidate already has, and missing skills. "
                "Utilize the provided semantic/vector overlaps between the resume and the job description "
                "to evaluate overall fit, transferable skills, and conceptual relevance, "
                "rather than strictly matching keywords. "
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

Semantic/Vector Overlaps Context:
{semantic_context}

Return the candidate-role match as structured data, evaluating based on semantic fit rather than pure keyword matching.

{format_instructions}
""",
            ),
        ]
    )
    chain = prompt | get_llm() | parser
    return invoke_llm_with_retries(
        lambda: chain.invoke(
            {
                "analysis_mode": analysis_mode,
                "desired_roles": ", ".join(desired_roles),
                "job_description": job_description or "Not provided",
                "semantic_context": semantic_context or "No vector-similarity overlaps computed.",
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
    chain = prompt | get_llm(temperature=0.2) | parser
    plan = invoke_llm_with_retries(
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
    plan.analysis_source = "deepseek_llm"
    plan.target_roles = target_roles
    plan.role_fit_score = skill_match.match_score
    return plan


from pydantic import BaseModel, Field

class InterviewQuestions(BaseModel):
    questions: list[str] = Field(min_length=5, max_length=5, description="List of exactly 5 interview questions")


class InterviewFeedback(BaseModel):
    feedback: str = Field(description="Detailed evaluation report of the candidate's answers, describing strengths and improvement areas")
    score: int = Field(description="Overall interview score from 0 to 100")


def generate_interview_questions(job_description: str, role: str) -> list[str]:
    parser = PydanticOutputParser(pydantic_object=InterviewQuestions)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an expert interviewer. Generate a list of exactly 5 relevant technical and behavioral "
                "interview questions for the specified candidate role based on the job description. "
                "Do not include introductory or general banter; focus on specific, challenging, and relevant questions. "
                "Return valid JSON matching the schema.",
            ),
            (
                "human",
                """
Target Role: {role}
Job Description: {job_description}

Generate exactly 5 interview questions based on the role and job description.

{format_instructions}
""",
            ),
        ]
    )
    chain = prompt | get_llm(temperature=0.5) | parser
    res = invoke_llm_with_retries(
        lambda: chain.invoke(
            {
                "role": role,
                "job_description": job_description or "Not provided",
                "format_instructions": parser.get_format_instructions(),
            }
        )
    )
    return res.questions


def evaluate_interview_responses(
    questions: list[str],
    answers: list[str],
    job_description: str,
    role: str
) -> dict:
    parser = PydanticOutputParser(pydantic_object=InterviewFeedback)
    transcript = ""
    for idx, (q, a) in enumerate(zip(questions, answers), start=1):
        transcript += f"Question {idx}: {q}\nCandidate Answer: {a or '[No Answer Provided]'}\n\n"

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an expert technical interviewer and hiring manager. Evaluate the candidate's "
                "interview transcript based on the role and job description. "
                "Return a detailed text feedback report and an overall score from 0 to 100. "
                "Be critical but constructive. Return valid JSON matching the schema.",
            ),
            (
                "human",
                """
Target Role: {role}
Job Description: {job_description}

Interview Transcript:
{transcript}

Evaluate this transcript. Provide constructive feedback outlining strengths and improvements, and a realistic score.

{format_instructions}
""",
            ),
        ]
    )
    chain = prompt | get_llm(temperature=0.2) | parser
    res = invoke_llm_with_retries(
        lambda: chain.invoke(
            {
                "role": role,
                "job_description": job_description or "Not provided",
                "transcript": transcript,
                "format_instructions": parser.get_format_instructions(),
            }
        )
    )
    return res.model_dump()

