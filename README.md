# CareerPilot – AI Career Readiness Evaluator

A candidate-focused AI career readiness MVP that analyzes a user's resume against desired roles or a specific job description, then generates SWOT analysis, skill gaps, a learning roadmap, likely interview questions, and interview prep.

## What It Does

- Upload a resume PDF or paste resume text
- Select desired roles
- Use Resume Only mode for general role readiness
- Use Resume + Job Description Fit mode for a specific job opening
- Get a match score, missing skills, SWOT analysis, roadmap, probable interview questions, and interview prep
- Download an AI-generated career readiness report as a PDF

## Stack

- Backend: FastAPI
- Frontend: Streamlit
- Resume parsing: PyMuPDF
- Agent workflow: LangGraph
- LLM orchestration: LangChain + ChatGroq
- LLM provider: Groq
- Groq API key: required

## Current AI Agent Setup

The app uses a LangGraph workflow where each analysis stage is powered by Groq through LangChain.

- LLM recruitment agent: `backend/agents/llm_recruitment_agent.py`
- Report generation agent: `backend/agents/report_generation_agent.py`
- LangGraph workflow: `backend/workflows/recruitment_workflow.py`

Set these environment variables before starting the backend:

```powershell
$env:GROQ_API_KEY="your-groq-api-key"
$env:GROQ_MODEL="llama-3.3-70b-versatile"
```

If `GROQ_API_KEY` is not set, the API returns a configuration error.

## Project Structure

```text
backend/
  agents/          Specialized recruitment agents
  api/             FastAPI route modules
  services/        PDF parsing and utility services
  workflows/       Orchestration layer
  main.py          FastAPI app entrypoint
frontend/
  app.py           Streamlit UI
database/          Placeholder for future migrations/schema
models/            Placeholder for local model artifacts
```

## Run Locally

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional Groq setup:

```powershell
Copy-Item .env.example .env
$env:GROQ_API_KEY="your-groq-api-key"
```

Start the backend:

```powershell
uvicorn backend.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```powershell
streamlit run frontend/app.py
```

Open the Streamlit URL shown in the terminal.

## API

Health check:

```http
GET /health
```

Analyze career readiness:

```http
POST /api/analyze
Content-Type: multipart/form-data

resume_file: PDF file, optional if resume_text is provided
resume_text: text, optional if resume_file is provided
desired_roles: comma-separated text, required
analysis_mode: resume_only or jd_fit
job_description: text, required only for jd_fit
```

## Next Steps

- Add recruiter/candidate accounts and saved report history
- Store candidates and reports in PostgreSQL
- Add ChromaDB for RAG over resumes, job descriptions, and preparation materials
- Add voice mock-interview mode with Whisper transcription
