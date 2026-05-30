"""
main.py
SlideForge AI — FastAPI Backend
Endpoints:
  POST /generate        — full pipeline: parse → outline → write → build
  POST /revise          — revision loop: apply feedback to existing deck
  GET  /download/{file} — download generated .pptx
  GET  /health          — health check
"""

import os
import json
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from tools.input_parser import parse_input
from agents.orchestrator import plan_outline
from agents.content_agent import write_all_slides
from agents.revision_agent import revise_deck
from tools.pptx_builder import build_pptx

load_dotenv()

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "generated")
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="SlideForge AI",
    description="AI-powered presentation generation using Groq + LangGraph",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────────

class GenerateTextRequest(BaseModel):
    text: str
    slide_count: Optional[str] = "auto"
    theme: Optional[str] = "corporate_blue"


class GenerateUrlRequest(BaseModel):
    url: str
    slide_count: Optional[str] = "auto"
    theme: Optional[str] = "corporate_blue"


class ReviseRequest(BaseModel):
    deck_title: str
    slides: list
    feedback: str
    theme: Optional[str] = "corporate_blue"
    version: Optional[int] = 2


# ── Helpers ───────────────────────────────────────────────────────────────────

def run_pipeline(content: str, slide_count: str, theme: str, version: int = 1) -> dict:
    """Full pipeline: content → outline → slides → pptx."""
    # Step 1: Plan outline
    outline = plan_outline(content, slide_count)

    # Step 2: Write slide content in parallel
    slides = write_all_slides(outline, content)

    # Step 3: Build PPTX
    filepath = build_pptx(
        deck_title=outline["deck_title"],
        slides=slides,
        theme_name=theme,
        output_dir=OUTPUT_DIR,
        version=version,
    )

    filename = Path(filepath).name

    return {
        "success": True,
        "deck_title": outline["deck_title"],
        "total_slides": len(slides),
        "theme": theme,
        "filename": filename,
        "download_url": f"/download/{filename}",
        "slides": slides,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "SlideForge AI", "model": os.getenv("GROQ_MODEL")}


@app.get("/themes")
def get_themes():
    return {
        "themes": [
            {"id": "corporate_blue", "name": "Corporate Blue", "description": "Navy & blue — professional B2B"},
            {"id": "midnight",       "name": "Midnight",       "description": "Deep dark with purple accent"},
            {"id": "clean_light",    "name": "Clean Light",    "description": "White & green — modern minimal"},
            {"id": "forest",         "name": "Forest",         "description": "Deep green — calm & natural"},
            {"id": "warm",           "name": "Warm",           "description": "Rich browns — elegant & warm"},
        ]
    }


@app.post("/generate/text")
async def generate_from_text(request: GenerateTextRequest):
    """Generate deck from plain text or topic."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text content cannot be empty.")
    try:
        content = parse_input("text", text=request.text)
        return run_pipeline(content, request.slide_count, request.theme)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/file")
async def generate_from_file(
    file: UploadFile = File(...),
    slide_count: str = Form("auto"),
    theme: str = Form("corporate_blue"),
):
    """Generate deck from uploaded PDF or DOCX file."""
    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        input_type = "pdf"
    elif filename.endswith(".docx"):
        input_type = "docx"
    else:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    try:
        file_bytes = await file.read()
        content = parse_input(input_type, file_bytes=file_bytes)
        if not content.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from the uploaded file.")
        return run_pipeline(content, slide_count, theme)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/url")
async def generate_from_url(request: GenerateUrlRequest):
    """Generate deck from a URL (web page scraping)."""
    if not request.url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    try:
        content = parse_input("url", url=request.url)
        if not content.strip():
            raise HTTPException(status_code=400, detail="Could not extract content from the URL.")
        return run_pipeline(content, request.slide_count, request.theme)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/revise")
async def revise(request: ReviseRequest):
    """Apply natural language feedback to an existing deck."""
    if not request.feedback.strip():
        raise HTTPException(status_code=400, detail="Feedback cannot be empty.")
    if not request.slides:
        raise HTTPException(status_code=400, detail="No slides provided for revision.")
    try:
        revised = revise_deck(request.slides, request.deck_title, request.feedback)
        updated_slides = revised.get("slides", request.slides)
        deck_title = revised.get("deck_title", request.deck_title)

        filepath = build_pptx(
            deck_title=deck_title,
            slides=updated_slides,
            theme_name=request.theme,
            output_dir=OUTPUT_DIR,
            version=request.version,
        )
        filename = Path(filepath).name

        return {
            "success": True,
            "deck_title": deck_title,
            "total_slides": len(updated_slides),
            "theme": request.theme,
            "filename": filename,
            "download_url": f"/download/{filename}",
            "slides": updated_slides,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{filename}")
def download_file(filename: str):
    """Download a generated .pptx file."""
    # Sanitize filename
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found. It may have expired.")
    return FileResponse(
        path=filepath,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=filename,
    )


@app.get("/files")
def list_files():
    """List all generated files."""
    files = sorted(Path(OUTPUT_DIR).glob("*.pptx"), key=os.path.getmtime, reverse=True)
    return {
        "files": [
            {"filename": f.name, "download_url": f"/download/{f.name}",
             "size_kb": round(f.stat().st_size / 1024, 1)}
            for f in files[:20]
        ]
    }
