from __future__ import annotations

from backend.models import CareerPrepPlan, ResumeProfile, SkillMatch


def generate_report(
    profile: ResumeProfile,
    skill_match: SkillMatch,
    prep_plan: CareerPrepPlan,
) -> str:
    missing = ", ".join(skill_match.missing_skills) or "No major missing skills detected"
    strengths = ", ".join(skill_match.strong_areas) or "Relevant experience needs manual review"
    roles = ", ".join(prep_plan.target_roles)
    mode_label = "Resume + Job Description Fit" if prep_plan.analysis_mode == "jd_fit" else "Resume Only"
    source_label = "Groq LLM via LangChain"
    questions = "\n".join(f"- {question}" for question in prep_plan.probable_interview_questions)
    roadmap = "\n".join(
        f"- {phase.title} ({phase.duration}): " + "; ".join(phase.actions)
        for phase in prep_plan.roadmap
    )
    prep = "\n".join(f"- {item}" for item in prep_plan.interview_prep)
    swot = prep_plan.swot_analysis

    return f"""AI Career Readiness Report

Target Roles: {roles}
Analysis Mode: {mode_label}
Analysis Source: {source_label}
Role Fit Score: {prep_plan.role_fit_score}/100

Candidate Summary:
{profile.summary}

Skill Match:
- Match Score: {skill_match.match_score}/100
- Strong Areas: {strengths}
- Missing Skills: {missing}

SWOT Analysis:
Strengths:
{chr(10).join(f"- {item}" for item in swot.strengths)}

Weaknesses:
{chr(10).join(f"- {item}" for item in swot.weaknesses)}

Opportunities:
{chr(10).join(f"- {item}" for item in swot.opportunities)}

Threats:
{chr(10).join(f"- {item}" for item in swot.threats)}

Roadmap:
{roadmap}

Probable Interview Questions:
{questions}

Interview Prep:
{prep}
"""
