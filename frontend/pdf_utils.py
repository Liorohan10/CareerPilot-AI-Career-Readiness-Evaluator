from __future__ import annotations

from io import BytesIO


def build_report_pdf(report_text: str) -> bytes:
    def escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines: list[str] = []
    for raw_line in report_text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        while len(line) > 95:
            lines.append(line[:95])
            line = line[95:]
        lines.append(line)

    content = BytesIO()
    content.write(b"BT\n/F1 10 Tf\n50 750 Td\n14 TL\n")
    for line in lines:
        content.write(f"({escape_pdf_text(line)}) Tj\nT*\n".encode("latin-1", errors="replace"))
    content.write(b"ET")
    stream = content.getvalue()

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = BytesIO()
    pdf.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(pdf.tell())
        pdf.write(f"{index} 0 obj\n".encode())
        pdf.write(obj)
        pdf.write(b"\nendobj\n")

    xref_start = pdf.tell()
    pdf.write(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.write(f"{offset:010d} 00000 n \n".encode())
    pdf.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode()
    )
    return pdf.getvalue()
