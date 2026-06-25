from pydantic import BaseModel, Field


class ResumeProfile(BaseModel):
    candidate_name: str = Field(default="Candidate", description="Name of the candidate extracted from the resume")
    candidate_email: str = Field(default="", description="Email of the candidate extracted from the resume")
    technical_skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    years_experience: float = 0
    summary: str


class SkillMatch(BaseModel):
    match_score: int
    missing_skills: list[str]
    strong_areas: list[str]
    required_skills: list[str]


class SWOTAnalysis(BaseModel):
    strengths: list[str] = Field(min_length=2)
    weaknesses: list[str] = Field(min_length=2)
    opportunities: list[str] = Field(min_length=2)
    threats: list[str] = Field(min_length=2)


class RoadmapPhase(BaseModel):
    title: str
    duration: str
    actions: list[str] = Field(min_length=2)


class CareerPrepPlan(BaseModel):
    analysis_mode: str
    analysis_source: str = "groq_llm"
    target_roles: list[str] = Field(min_length=1)
    role_fit_score: int
    swot_analysis: SWOTAnalysis
    roadmap: list[RoadmapPhase] = Field(min_length=3)
    probable_interview_questions: list[str] = Field(min_length=5)
    interview_prep: list[str] = Field(min_length=4)


class RecruitmentReport(BaseModel):
    application_id: int | None = None
    resume_profile: ResumeProfile
    skill_match: SkillMatch
    career_prep_plan: CareerPrepPlan
    report: str


class InterviewStatusResponse(BaseModel):
    application_id: int
    role: str
    status: str
    current_question_index: int
    total_questions: int
    current_question: str | None
    completed: bool
    feedback: str | None
    score: int | None
    questions: list[str] = Field(default_factory=list)
    answers: list[str] = Field(default_factory=list)



class InterviewSubmitAnswerRequest(BaseModel):
    answer: str

