from __future__ import annotations

import logging
import numpy as np
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter


logger = logging.getLogger(__name__)

_model = None

def get_embedding_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Load small, fast local embedding model
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as exc:
            logger.error("Failed to load sentence-transformers model: %s", exc)
            # Return None or raise
            raise RuntimeError("sentence-transformers could not be loaded") from exc
    return _model


def chunk_text(text: str, chunk_size: int = 400, chunk_overlap: int = 50) -> list[str]:
    if not text or not text.strip():
        return []
    try:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )
        return splitter.split_text(text)
    except Exception as exc:
        logger.warning("RecursiveCharacterTextSplitter failed, falling back to simple sentence split. Error: %s", exc)
        # Simple fallback
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        for p in paragraphs:
            if len(p) <= chunk_size:
                chunks.append(p)
            else:
                # split paragraphs into sentences roughly
                sentences = p.split(". ")
                current_chunk = ""
                for s in sentences:
                    if len(current_chunk) + len(s) + 2 <= chunk_size:
                        current_chunk += (s + ". ")
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = s + ". "
                if current_chunk:
                    chunks.append(current_chunk.strip())
        return chunks


def compute_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def get_semantic_overlaps(resume_text: str, jd_text: str, top_k: int = 5) -> str:
    """
    Chunks both resume and job description, vectorizes them, and retrieves
    the top K most semantically similar chunks/overlaps between resume and JD.
    """
    if not resume_text or not jd_text:
        return "No semantic matches could be calculated because either the resume or job description is empty."

    try:
        model = get_embedding_model()
        resume_chunks = chunk_text(resume_text, chunk_size=350, chunk_overlap=30)
        jd_chunks = chunk_text(jd_text, chunk_size=350, chunk_overlap=30)

        if not resume_chunks or not jd_chunks:
            return "No semantic matching chunks found."

        # Compute embeddings
        resume_embeddings = model.encode(resume_chunks, convert_to_numpy=True)
        jd_embeddings = model.encode(jd_chunks, convert_to_numpy=True)

        matches = []
        for i, jd_chunk in enumerate(jd_chunks):
            for j, res_chunk in enumerate(resume_chunks):
                sim = compute_cosine_similarity(jd_embeddings[i], resume_embeddings[j])
                matches.append({
                    "jd_chunk": jd_chunk,
                    "resume_chunk": res_chunk,
                    "similarity": sim
                })

        # Sort matches by similarity descending
        matches.sort(key=lambda x: x["similarity"], reverse=True)

        # Deduplicate matches to show distinct parts
        seen_jd = set()
        seen_res = set()
        deduped_matches = []
        for m in matches:
            if m["jd_chunk"] not in seen_jd and m["resume_chunk"] not in seen_res:
                seen_jd.add(m["jd_chunk"])
                seen_res.add(m["resume_chunk"])
                deduped_matches.append(m)
                if len(deduped_matches) >= top_k:
                    break

        if not deduped_matches:
            return "No strong semantic matches found between the resume and job description."

        context_str = "Top Semantic Matches (Resume vs Job Description):\n"
        for idx, match in enumerate(deduped_matches, start=1):
            context_str += (
                f"{idx}. JD requirement section:\n   \"{match['jd_chunk']}\"\n"
                f"   Candidate matching profile section (similarity: {match['similarity']:.2f}):\n"
                f"   \"{match['resume_chunk']}\"\n\n"
            )
        return context_str
    except Exception as exc:
        logger.error("Error computing semantic overlaps: %s", exc)
        return f"Semantic matching skipped due to system error: {str(exc)}"
