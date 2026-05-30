"""
agents/orchestrator.py
Orchestrator Agent — uses Groq (llama-3.3-70b-versatile) to plan
the full slide deck outline from the parsed input content.
Returns a structured list of slide outlines (title + key_points).
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

ORCHESTRATOR_SYSTEM = """You are a professional presentation architect.
Your job is to analyze content and produce a structured slide deck outline.

Rules:
- Always return ONLY valid JSON — no markdown, no explanation, no code fences
- Produce between 6 and 12 slides depending on content length
- Always start with a title slide and end with a closing/thank you slide
- Keep slide titles short (max 6 words)
- Each slide gets 3-5 key_points (short phrases, not full sentences)
- Assign a layout to each slide: "title", "content", "two_column", "quote", "closing"
- The first slide must have layout "title", the last must have layout "closing"

Return this exact JSON structure:
{
  "deck_title": "Full deck title here",
  "total_slides": 8,
  "slides": [
    {
      "index": 1,
      "title": "Slide Title",
      "layout": "title",
      "key_points": ["point 1", "point 2", "point 3"],
      "speaker_note": "Brief speaker note for this slide."
    }
  ]
}"""


def plan_outline(content: str, slide_count: str = "auto") -> dict:
    """
    Takes parsed content string, returns a slide outline dict.
    slide_count: 'auto' or a number string like '8', '10'
    """
    count_instruction = (
        "Choose the optimal number of slides (6–12) based on content length."
        if slide_count == "auto"
        else f"Produce exactly {slide_count} slides (adjust content to fit)."
    )

    user_prompt = f"""Analyze the following content and create a professional slide deck outline.
{count_instruction}

CONTENT:
{content[:6000]}

Return only the JSON outline. No other text."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()

    # Strip accidental markdown fences if model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        outline = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Orchestrator returned invalid JSON: {e}\nRaw: {raw[:500]}")

    return outline
