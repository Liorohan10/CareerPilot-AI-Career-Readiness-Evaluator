from __future__ import annotations

import requests
import streamlit as st

from frontend.pdf_utils import build_report_pdf

API_URL = "http://localhost:8000/api/analyze"
ROLE_OPTIONS = [
    "AI/ML Engineer",
    "Data Scientist",
    "Backend Developer",
    "Frontend Developer",
    "Full Stack Developer",
    "DevOps Engineer",
    "Data Engineer",
]


st.set_page_config(page_title="AI Recruitment Agent", page_icon=":briefcase:", layout="wide")

st.title("AI Recruitment Agent")
st.caption("Career readiness and interview preparation workspace")

mode_label = st.radio(
    "Analysis Mode",
    ["Resume Only", "Resume + Job Description Fit"],
    horizontal=True,
)
analysis_mode = "jd_fit" if mode_label == "Resume + Job Description Fit" else "resume_only"

with st.sidebar:
    st.header("Your Profile")
    resume_file = st.file_uploader("Resume PDF", type=["pdf"])
    resume_text = st.text_area("Or paste resume text", height=180)
    desired_roles = st.multiselect(
        "Desired Roles",
        ROLE_OPTIONS,
        default=["AI/ML Engineer"],
    )
    custom_role_text = st.text_input(
        "Custom Role",
        placeholder="Add a role if it is not listed",
    )

job_description = ""
if analysis_mode == "jd_fit":
    job_description = st.text_area(
        "Job Description",
        height=180,
        placeholder="Paste the job description to evaluate fit against its required skills and experience.",
    )

button_label = "Analyze Resume" if analysis_mode == "resume_only" else "Evaluate JD Fit"
submitted = st.button(button_label, type="primary", use_container_width=True)

if submitted:
    custom_roles = [role.strip() for role in custom_role_text.split(",") if role.strip()]
    selected_roles = list(dict.fromkeys(desired_roles + custom_roles))

    if not resume_file and not resume_text.strip():
        st.error("Please upload a resume PDF or paste resume text.")
    elif not selected_roles:
        st.error("Please select at least one desired role.")
    elif analysis_mode == "jd_fit" and not job_description.strip():
        st.error("Please paste a job description for JD fit mode.")
    else:
        files = {}
        data = {
            "job_description": job_description,
            "resume_text": resume_text,
            "desired_roles": ",".join(selected_roles),
            "analysis_mode": analysis_mode,
        }
        if resume_file:
            files["resume_file"] = (resume_file.name, resume_file.getvalue(), "application/pdf")

        with st.spinner("Building your career readiness plan..."):
            try:
                response = requests.post(API_URL, data=data, files=files, timeout=60)
                response.raise_for_status()
                result = response.json()
            except requests.exceptions.ConnectionError:
                st.error("Backend is not running. Start it with: uvicorn backend.main:app --reload --port 8000")
                st.stop()
            except requests.HTTPError as exc:
                st.error(f"Analysis failed: {exc.response.text}")
                st.stop()

        match = result["skill_match"]
        prep_plan = result["career_prep_plan"]
        swot = prep_plan["swot_analysis"]

        metric_cols = st.columns(3)
        metric_cols[0].metric("Match Score", f"{match['match_score']}/100")
        metric_cols[1].metric("Role Fit", f"{prep_plan['role_fit_score']}/100")
        metric_cols[2].metric("Mode", "JD Fit" if prep_plan["analysis_mode"] == "jd_fit" else "Resume Only")
        st.caption("Analysis source: Groq LLM via LangChain and LangGraph")

        left, right = st.columns([1, 1])
        with left:
            st.subheader("Strong Areas")
            for skill in match["strong_areas"] or ["Needs manual review"]:
                st.write(f"- {skill}")
            st.subheader("Missing Skills")
            for skill in match["missing_skills"] or ["No major gaps detected"]:
                st.write(f"- {skill}")
            st.subheader("Interview Prep")
            for item in prep_plan["interview_prep"]:
                st.write(f"- {item}")

        with right:
            st.subheader("Probable Interview Questions")
            for question in prep_plan["probable_interview_questions"]:
                st.write(f"- {question}")

        st.subheader("SWOT Analysis")
        swot_cols = st.columns(4)
        for column, title, values in [
            (swot_cols[0], "Strengths", swot["strengths"]),
            (swot_cols[1], "Weaknesses", swot["weaknesses"]),
            (swot_cols[2], "Opportunities", swot["opportunities"]),
            (swot_cols[3], "Threats", swot["threats"]),
        ]:
            with column:
                st.markdown(f"**{title}**")
                for value in values:
                    st.write(f"- {value}")

        st.subheader("Roadmap")
        for phase in prep_plan["roadmap"]:
            with st.expander(f"{phase['title']} - {phase['duration']}", expanded=True):
                for action in phase["actions"]:
                    st.write(f"- {action}")

        st.subheader("AI-Generated Career Report")
        st.text_area("Report", result["report"], height=360)
        st.download_button(
            "Download Report PDF",
            data=build_report_pdf(result["report"]),
            file_name="ai-career-readiness-report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
