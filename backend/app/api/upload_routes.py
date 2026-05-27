"""POST /api/upload/resume — extract text/JSON from an uploaded resume.

Returns:
  - { "kind": "json", "resume": {...} }     when a JSON resume is uploaded
  - { "kind": "text", "text": "..." }       when a PDF / TXT / DOCX is uploaded
"""
import io
import json

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/api/upload", tags=["upload"])

_MAX_BYTES = 20 * 1024 * 1024  # 20 MB


def _extract_pdf_text(data: bytes) -> str:
    """Best-effort PDF text extraction. Tries pypdf, falls back to pdfminer."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        chunks = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
                chunks.append(t.strip())
            except Exception:
                continue
        text = "\n\n".join(c for c in chunks if c)
        if text.strip():
            return text
    except Exception:
        pass
    try:
        from pdfminer.high_level import extract_text
        return extract_text(io.BytesIO(data)) or ""
    except Exception as e:
        raise HTTPException(400, f"Could not parse PDF: {e}")


def _extract_docx_text(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        raise HTTPException(400, f"Could not parse DOCX: {e}")


@router.post("/resume")
async def upload_resume(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > _MAX_BYTES:
        raise HTTPException(400, f"File too large (max {_MAX_BYTES // (1024*1024)} MB)")

    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()

    # JSON resume
    if name.endswith(".json") or "json" in ctype:
        try:
            parsed = json.loads(data.decode("utf-8", errors="replace"))
        except Exception as e:
            raise HTTPException(400, f"Invalid JSON: {e}")
        if not isinstance(parsed, dict):
            raise HTTPException(400, "JSON must be an object at the top level")
        return {"kind": "json", "filename": file.filename, "resume": parsed}

    # PDF
    if name.endswith(".pdf") or "pdf" in ctype:
        text = _extract_pdf_text(data)
        return {"kind": "text", "filename": file.filename, "format": "pdf",
                "text": text, "char_count": len(text)}

    # DOCX
    if name.endswith(".docx") or "officedocument.wordprocessingml" in ctype:
        text = _extract_docx_text(data)
        return {"kind": "text", "filename": file.filename, "format": "docx",
                "text": text, "char_count": len(text)}

    # Plain text
    if name.endswith(".txt") or "text/plain" in ctype:
        text = data.decode("utf-8", errors="replace")
        return {"kind": "text", "filename": file.filename, "format": "txt",
                "text": text, "char_count": len(text)}

    raise HTTPException(400, f"Unsupported file type: {file.filename or ctype or 'unknown'}")
