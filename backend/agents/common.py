from __future__ import annotations

import re
from collections import Counter

TECH_SKILLS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "next.js",
    "node.js",
    "fastapi",
    "django",
    "flask",
    "sql",
    "postgresql",
    "mysql",
    "mongodb",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "git",
    "linux",
    "machine learning",
    "deep learning",
    "nlp",
    "langchain",
    "langgraph",
    "chromadb",
    "rag",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "spark",
    "airflow",
    "rest api",
    "graphql",
    "microservices",
    "ci/cd",
    "html",
    "css",
    "statistics",
    "terraform",
}

EDUCATION_TERMS = {
    "b.tech",
    "bachelor",
    "master",
    "m.tech",
    "mba",
    "phd",
    "degree",
    "computer science",
    "engineering",
}

CERTIFICATION_TERMS = {
    "certified",
    "certification",
    "aws certified",
    "azure certified",
    "google cloud",
    "scrum",
    "pmp",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def extract_known_skills(text: str) -> list[str]:
    normalized = normalize_text(text)
    skills = [skill for skill in TECH_SKILLS if skill in normalized]
    return sorted(skills)


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def extract_keyword_phrases(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z.+#/-]{2,}", normalize_text(text))
    stopwords = {
        "and",
        "the",
        "for",
        "with",
        "you",
        "our",
        "are",
        "will",
        "this",
        "that",
        "from",
        "have",
        "has",
        "using",
        "work",
        "team",
        "role",
        "candidate",
        "experience",
        "knowledge",
    }
    useful = [word for word in words if word not in stopwords]
    return [word for word, _ in Counter(useful).most_common(limit)]


def clamp_score(value: float) -> int:
    return max(0, min(100, round(value)))
