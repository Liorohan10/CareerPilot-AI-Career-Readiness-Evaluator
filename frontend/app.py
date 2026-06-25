from __future__ import annotations

import requests
import streamlit as st
import json

from frontend.pdf_utils import build_report_pdf

API_BASE = "http://localhost:8000/api"
ROLE_OPTIONS = [
    "AI/ML Engineer",
    "Data Scientist",
    "Backend Developer",
    "Frontend Developer",
    "Full Stack Developer",
    "DevOps Engineer",
    "Data Engineer",
]

st.set_page_config(page_title="AI Recruitment Workspace", page_icon=":briefcase:", layout="wide")

# Premium Custom CSS
st.markdown("""
<style>
    /* Styling headers and fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-title {
        font-size: 3rem !important;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.1rem;
    }
    
    .subtitle {
        font-size: 1.2rem;
        color: #888899;
        margin-bottom: 2rem;
    }
    
    .section-card {
        background-color: #1a1c24;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2e303d;
        margin-bottom: 1.5rem;
    }
    
    .badge-interview {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }

    .badge-screen {
        background: linear-gradient(135deg, #ff9966 0%, #ff5e62 100%);
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Application Header
st.markdown("<h1 class='main-title'>AI Recruitment Agent</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Unified screening workspace & interactive interview suite</p>", unsafe_allow_html=True)

# Navigation Menu
menu = st.sidebar.radio(
    "Navigation Portal",
    ["💼 Recruitment Hub (Apply)", "🎓 Candidate Portal", "🕵️ Recruiter Dashboard"],
    index=0
)

# ----------------- 💼 RECRUITMENT HUB -----------------
if menu == "💼 Recruitment Hub (Apply)":
    st.header("Upload Profile & Resume")
    st.caption("Apply for a position and get evaluated instantly using semantic vector matching.")
    
    mode_label = st.radio(
        "Screening Mode",
        ["Resume Only", "Resume + Job Description Fit"],
        horizontal=True,
    )
    analysis_mode = "jd_fit" if mode_label == "Resume + Job Description Fit" else "resume_only"

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Candidate Information")
        resume_file = st.file_uploader("Upload Resume PDF", type=["pdf"])
        resume_text = st.text_area("Or paste resume text", height=200)
        desired_roles = st.multiselect(
            "Desired Target Roles",
            ROLE_OPTIONS,
            default=["AI/ML Engineer"],
        )
        custom_role_text = st.text_input(
            "Custom Target Role",
            placeholder="e.g. Lead QA Engineer",
        )
        
    with col2:
        job_description = ""
        if analysis_mode == "jd_fit":
            st.subheader("Job Details")
            job_description = st.text_area(
                "Job Description",
                height=320,
                placeholder="Paste the job description requirements to evaluate semantic fit.",
            )
        else:
            st.info("💡 Switch to 'Resume + Job Description Fit' to evaluate fit against a specific job role and get matched via semantic vector comparison.")

    button_label = "Evaluate Candidate Fit" if analysis_mode == "jd_fit" else "Analyze Resume Profile"
    submitted = st.button(button_label, type="primary", use_container_width=True)

    if submitted:
        custom_roles = [role.strip() for role in custom_role_text.split(",") if role.strip()]
        selected_roles = list(dict.fromkeys(desired_roles + custom_roles))

        if not resume_file and not resume_text.strip():
            st.error("Please upload a resume PDF or paste resume text.")
        elif not selected_roles:
            st.error("Please select at least one target role.")
        elif analysis_mode == "jd_fit" and not job_description.strip():
            st.error("Please paste a job description for JD fit evaluation.")
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

            with st.spinner("Processing profile through LangGraph recruitment workflow..."):
                try:
                    response = requests.post(f"{API_BASE}/analyze", data=data, files=files, timeout=60)
                    response.raise_for_status()
                    result = response.json()
                except requests.exceptions.ConnectionError:
                    st.error("Backend server is not running. Please start it on port 8000.")
                    st.stop()
                except requests.HTTPError as exc:
                    st.error(f"Analysis failed: {exc.response.text}")
                    st.stop()

            # Store the resulting Application ID in the session state for candidate portal access
            app_id = result.get("application_id")
            if app_id:
                st.session_state["last_app_id"] = app_id

            match = result["skill_match"]
            prep_plan = result["career_prep_plan"]
            swot = prep_plan["swot_analysis"]

            # Visual Feedback Success Banner
            if app_id:
                st.success(f"🎉 Application Saved! Your unique Candidate Application ID is: **{app_id}**")
                if match["match_score"] >= 70:
                    st.info("✨ Based on your high fit score, you have been selected to progress to the interview round! Head over to the **Candidate Portal** tab to take your interview.")
                else:
                    st.warning("Your screening results are ready. Below is your career roadmap. You did not meet the 70/100 threshold for an interview this time.")

            metric_cols = st.columns(3)
            metric_cols[0].metric("Match Score", f"{match['match_score']}/100")
            metric_cols[1].metric("Role Fit", f"{prep_plan['role_fit_score']}/100")
            metric_cols[2].metric("Mode", "JD Fit" if prep_plan["analysis_mode"] == "jd_fit" else "Resume Only")

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
                st.subheader("Suggested Practice Questions")
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
            st.text_area("Report", result["report"], height=300)
            st.download_button(
                "Download Report PDF",
                data=build_report_pdf(result["report"]),
                file_name=f"recruitment-report-{app_id or 'eval'}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

# ----------------- 🎓 CANDIDATE PORTAL -----------------
elif menu == "🎓 Candidate Portal":
    st.header("Candidate Interview & Dashboard Portal")
    st.caption("Access your application status and complete your assigned interviews here.")
    
    # Pre-populate Application ID if available in session state
    default_id = str(st.session_state.get("last_app_id", ""))
    app_id_input = st.text_input("Enter your Candidate Application ID", value=default_id)
    
    if app_id_input:
        try:
            app_id = int(app_id_input)
        except ValueError:
            st.error("Please enter a valid integer Application ID.")
            st.stop()
            
        with st.spinner("Fetching application details..."):
            try:
                response = requests.get(f"{API_BASE}/applications/{app_id}", timeout=10)
                if response.status_code == 404:
                    st.error("Application ID not found. Go back to Recruitment Hub to apply.")
                    st.stop()
                response.raise_for_status()
                app = response.json()
            except Exception as e:
                st.error(f"Error connecting to backend: {e}")
                st.stop()
                
        candidate_name = app.get("candidate_name", "Candidate")
        fit_score = app.get("fit_score", 0)
        status = app.get("status", "")
        role = app.get("job_title") or "Selected Position"
        
        st.markdown(f"### Welcome back, **{candidate_name}**!")
        st.markdown(f"**Applied Position:** {role} | **Screening Score:** {fit_score}/100")
        
        # Check eligibility
        if fit_score < 70:
            st.warning("🔒 You are not currently progressed to the interview stage because your screening score is below the 70 threshold.")
            
            # Show roadmap to help them improve
            st.subheader("Suggested Development Plan")
            try:
                plan = app["career_prep_plan"]
                st.write(f"**Coach Summary:** {app['resume_profile']['summary']}")
                for phase in plan["roadmap"]:
                    with st.expander(f"{phase['title']} - {phase['duration']}", expanded=True):
                        for action in phase["actions"]:
                            st.write(f"- {action}")
            except Exception:
                st.info("No roadmap details stored.")
        else:
            # Progressed to interview
            st.markdown("<span class='badge-interview'>🚀 Selected for Interview Round</span>", unsafe_allow_html=True)
            st.write("---")
            
            # Get interview status
            interview_response = requests.get(f"{API_BASE}/interviews/{app_id}", timeout=10)
            
            if interview_response.status_code == 404:
                # Interview is scheduled but not started
                st.info("You have a pending interview round scheduled for this role.")
                if st.button("🚀 Start Interview Now", type="primary", use_container_width=True):
                    with st.spinner("Preparing interview environment..."):
                        start_res = requests.post(f"{API_BASE}/interviews/{app_id}/start", timeout=20)
                        if start_res.status_code == 200:
                            st.success("Questions generated! Retrying...")
                            st.rerun()
                        else:
                            st.error("Failed to start interview.")
            else:
                interview = interview_response.json()
                int_status = interview.get("status")
                
                if int_status == "completed":
                    # Interview is completed
                    st.success("🎉 You have completed the interview round! Below is your feedback.")
                    
                    st.metric("Interview Performance Score", f"{interview['score']}/100")
                    st.subheader("Hiring Manager Feedback")
                    st.write(interview["feedback"])
                
                elif int_status in ("scheduled", "ongoing"):
                    # Ongoing interview
                    curr_idx = interview.get("current_question_index", 0)
                    total_q = interview.get("total_questions", 5)
                    curr_q = interview.get("current_question", "")
                    
                    st.subheader(f"Question {curr_idx + 1} of {total_q}")
                    st.markdown(f"##### *\"{curr_q}\"*")
                    
                    # Text area for answer
                    st.write("")
                    candidate_answer = st.text_area("Your Response", height=150, placeholder="Type your answer here. Provide technical details or examples where relevant.")
                    
                    if st.button("Submit Answer & Next", type="primary"):
                        if not candidate_answer.strip():
                            st.error("Answer cannot be empty. Please type a response.")
                        else:
                            with st.spinner("Submitting answer..."):
                                submit_res = requests.post(
                                    f"{API_BASE}/interviews/{app_id}/submit",
                                    json={"answer": candidate_answer},
                                    timeout=60
                                )
                                if submit_res.status_code == 200:
                                    st.rerun()
                                else:
                                    st.error("Failed to submit response.")

# ----------------- 🕵️ RECRUITER DASHBOARD -----------------
elif menu == "🕵️ Recruiter Dashboard":
    st.header("Recruiter Overview Dashboard")
    st.caption("Monitor candidate pipelines, review semantic resumes, and analyze interview feedback.")
    
    with st.spinner("Loading candidates..."):
        try:
            response = requests.get(f"{API_BASE}/recruiter/applications", timeout=10)
            response.raise_for_status()
            applications = response.json()
        except Exception as e:
            st.error(f"Error fetching data from backend: {e}")
            st.stop()
            
    if not applications:
        st.info("No candidate applications have been processed yet.")
    else:
        # Construct summary lists for selectbox
        candidate_options = {}
        for app in applications:
            label = f"ID {app['id']}: {app['candidate_name']} ({app['job_title'] or 'Resume Only'} - Screen Score: {app['fit_score']}/100)"
            candidate_options[label] = app["id"]
            
        selected_label = st.selectbox("Select Candidate Application", list(candidate_options.keys()))
        selected_app_id = candidate_options[selected_label]
        
        # Load complete detail
        with st.spinner("Loading candidate detail..."):
            detail_res = requests.get(f"{API_BASE}/applications/{selected_app_id}", timeout=10)
            app_detail = detail_res.json()
            
        st.write("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("Candidate Information")
            st.markdown(f"**Name:** {app_detail['candidate_name']}")
            st.markdown(f"**Email:** {app_detail['candidate_email']}")
            st.markdown(f"**Applied On:** {app_detail['created_at'][:10]}")
            st.markdown(f"**Screening Status:** `{app_detail['status']}`")
        with col2:
            st.subheader("Fit Scores")
            st.metric("Resume Match Score", f"{app_detail['fit_score']}/100")
            
        # Tabs for details
        tab1, tab2 = st.tabs(["📄 Resume Screening & Roadmap", "💬 Interview Transcript & Evaluation"])
        
        with tab1:
            try:
                st.subheader("Resume Technical Summary")
                st.write(app_detail["resume_profile"]["summary"])
                
                st.subheader("Technical Skills & Projects")
                st.write(f"**Skills:** {', '.join(app_detail['resume_profile']['technical_skills'])}")
                st.write(f"**Projects:** {', '.join(app_detail['resume_profile']['projects'])}")
                
                st.subheader("SWOT Evaluation")
                swot = app_detail["career_prep_plan"]["swot_analysis"]
                swot_cols = st.columns(4)
                for column, title, values in [
                    (swot_cols[0], "Strengths", swot["strengths"]),
                    (swot_cols[1], "Weaknesses", swot["weaknesses"]),
                    (swot_cols[2], "Opportunities", swot["opportunities"]),
                    (swot_cols[3], "Threats", swot["threats"]),
                ]:
                    with column:
                        st.markdown(f"**{title}**")
                        for v in values:
                            st.write(f"- {v}")
            except Exception:
                st.warning("Resume screening profile data not fully parsed.")
                
        with tab2:
            # Load interview transcript
            int_res = requests.get(f"{API_BASE}/interviews/{selected_app_id}", timeout=10)
            if int_res.status_code == 404:
                st.info("No interview transcript available. The candidate has not started their interview round yet.")
            else:
                interview = int_res.json()
                st.subheader("Interview Status")
                st.write(f"**Status:** `{interview['status'].upper()}`")
                
                if interview["status"] == "completed":
                    st.metric("Hiring Manager Interview Score", f"{interview['score']}/100")
                    st.subheader("Interview Evaluation Report")
                    st.write(interview["feedback"])
                
                # Show transcript questions and answers
                st.subheader("Interview Transcript Q&A")

                
                # Fetch full interview including answers from routes
                try:
                    # Let's display the QA
                    # If we don't have answers yet in the response, let's load it from the API
                    # Let's check if the API returns answers. We will make sure the API returns answers by modifying it.
                    st.write("Below are the candidate's answers to the questions:")
                    # We will ensure the API has the questions and answers list
                    # Let's modify the routes to return the answers list
                    # For now, let's write the display code assuming the api returns it
                    # (we will modify the model and routes to include it right after)
                    st.write("")
                    for i, q in enumerate(interview.get("questions", [])):
                        ans_list = interview.get("answers", [])
                        ans = ans_list[i] if i < len(ans_list) else ""
                        with st.chat_message("assistant"):
                            st.write(f"**Question {i+1}:** {q}")
                        if ans:
                            with st.chat_message("user"):
                                st.write(ans)
                        else:
                            st.write("*No response yet*")
                except Exception as e:
                    st.error(f"Error displaying Q&A: {e}")
