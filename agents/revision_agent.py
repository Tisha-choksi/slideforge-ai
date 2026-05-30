"""
agents/revision_agent.py
Revision Agent — takes the current deck slides + user feedback
and surgically edits only the affected slides.
Does NOT regenerate the entire deck.
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

REVISION_SYSTEM = """You are a presentation revision assistant.
You receive a current slide deck (as JSON) and user feedback.
Your job is to make targeted edits — only change what the feedback asks for.

Rules:
- Return ONLY valid JSON — no markdown, no explanation, no code fences
- Only modify slides mentioned in the feedback
- If adding a new slide, insert it at the correct position and re-index all slides
- If deleting a slide, remove it and re-index
- Keep all unchanged slides exactly as they are
- Return the COMPLETE updated slides array

Return this exact structure:
{
  "deck_title": "Same or updated title",
  "slides": [ ...complete updated slides array... ]
}"""


def revise_deck(current_slides: list, deck_title: str, feedback: str) -> dict:
    """
    Apply user feedback to the current deck.
    Returns updated deck dict with revised slides.
    """
    current_json = json.dumps({
        "deck_title": deck_title,
        "slides": current_slides
    }, indent=2)

    user_prompt = f"""Here is the current deck:
{current_json}

User feedback:
{feedback}

Apply the feedback and return the complete updated deck JSON."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REVISION_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=3000,
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        revised = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Revision agent returned invalid JSON: {e}\nRaw: {raw[:500]}")

    return revised
