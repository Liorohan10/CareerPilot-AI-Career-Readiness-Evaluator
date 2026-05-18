from __future__ import annotations

import fitz


def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts: list[str] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as document:
        for page in document:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()
