"""
agents/content_agent.py
Content Agent — takes the orchestrator outline and fills each slide
with full bullet text and speaker notes using Groq.
All slides are generated in parallel using ThreadPoolExecutor.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

CONTENT_SYSTEM = """You are a professional slide content writer.
Your job is to write polished, concise slide content based on a slide brief.

Rules:
- Return ONLY valid JSON — no markdown, no explanation, no code fences
- Bullets must be complete, meaningful sentences (not just keywords)
- Keep bullets under 15 words each
- Speaker notes should be 1-2 sentences the presenter would say
- For layout "title": write a subtitle instead of bullets
- For layout "closing": write a 1-line thank you message and contact prompt
- For layout "two_column": provide left_bullets and right_bullets (3 each)
- For all other layouts: provide 3-5 bullets

Return this exact JSON:
{
  "index": 1,
  "title": "Slide Title",
  "layout": "content",
  "subtitle": null,
  "bullets": ["Bullet one here.", "Bullet two here."],
  "left_bullets": null,
  "right_bullets": null,
  "speaker_note": "What the presenter says here."
}"""


def write_slide(slide_brief: dict, source_content: str) -> dict:
    """Write full content for a single slide."""
    user_prompt = f"""Write content for this slide:

Slide Index: {slide_brief['index']}
Title: {slide_brief['title']}
Layout: {slide_brief['layout']}
Key Points to Cover: {', '.join(slide_brief.get('key_points', []))}

Source material for context:
{source_content[:3000]}

Return only the JSON object."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": CONTENT_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        slide = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: use the outline data if JSON parsing fails
        slide = {
            "index": slide_brief["index"],
            "title": slide_brief["title"],
            "layout": slide_brief["layout"],
            "subtitle": None,
            "bullets": slide_brief.get("key_points", ["Content coming soon."]),
            "left_bullets": None,
            "right_bullets": None,
            "speaker_note": slide_brief.get("speaker_note", ""),
        }

    return slide


def write_all_slides(outline: dict, source_content: str) -> list:
    """
    Write content for all slides in parallel.
    Returns list of completed slide dicts sorted by index.
    """
    slides_brief = outline.get("slides", [])
    completed = {}

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(write_slide, slide, source_content): slide["index"]
            for slide in slides_brief
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                completed[idx] = result
            except Exception as e:
                # Fallback slide on error
                brief = next(s for s in slides_brief if s["index"] == idx)
                completed[idx] = {
                    "index": idx,
                    "title": brief["title"],
                    "layout": brief.get("layout", "content"),
                    "subtitle": None,
                    "bullets": brief.get("key_points", ["Content generation failed."]),
                    "left_bullets": None,
                    "right_bullets": None,
                    "speaker_note": "",
                }

    return [completed[i] for i in sorted(completed.keys())]
