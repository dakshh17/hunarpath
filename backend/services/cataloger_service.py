"""
HunarPath - Structured Cataloger Service.

Extracts structured product metadata from an artisan's free-form
transcript using a local Ollama LLM (qwen2.5:1.5b / llama3).  Falls
back to a rule-based regex parser when the Ollama daemon is unreachable.

Strict grounding policy: the system prompt forbids hallucinated
certifications, marketing embellishments, or facts not present in the
artisan's own words.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
HTTP_TIMEOUT: float = 30.0

# ---------------------------------------------------------------------------
# System prompt - strict fact-grounding
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are HunarPath Cataloger, a structured data extraction engine for \
Indian handicraft products.

RULES (absolute):
1. Extract ONLY facts explicitly stated by the artisan.  NEVER invent \
   certifications (GI tag, ISO, etc.), awards, or marketing superlatives \
   that are not mentioned.
2. If a field is not mentioned, set it to null.
3. Output MUST be a single valid JSON object - no markdown fences, no \
   commentary.
4. Generate professional yet truthful `title_en`, `title_hi`, \
   `description_en`, and `description_hi` based strictly on extracted facts.

OUTPUT SCHEMA:
{
  "craft_type": "<string or null>",
  "material": "<string or null>",
  "primary_color": "<string or null>",
  "labor_days": <number or null>,
  "raw_cost": <number or null>,
  "title_en": "<string>",
  "title_hi": "<string>",
  "description_en": "<string>",
  "description_hi": "<string>"
}
"""

_USER_PROMPT_TEMPLATE = """\
Artisan transcript:
\"\"\"
{transcript}
\"\"\"

Extract the structured product catalog entry as JSON.
"""

# ---------------------------------------------------------------------------
# Craft vocabulary for regex fallback
# ---------------------------------------------------------------------------
_CRAFT_KEYWORDS: dict[str, str] = {
    "saree": "Saree Weaving",
    "sari": "Saree Weaving",
    "dupatta": "Handloom Weaving",
    "shawl": "Handloom Weaving",
    "stole": "Handloom Weaving",
    "cushion": "Embroidery",
    "bag": "Embroidery",
    "figurine": "Bell Metal Craft",
    "dhokra": "Bell Metal Craft",
    "bell metal": "Bell Metal Craft",
    "mask": "Wood Carving",
    "pot": "Terracotta",
    "diya": "Bell Metal Craft",
    "clutch": "Zari & Brocade",
    "brocade": "Zari & Brocade",
    "zari": "Zari & Brocade",
    "meenakari": "Meenakari",
    "block print": "Block Printing",
    "ajrakh": "Block Printing",
    "mirror work": "Mirror Work",
    "wind chime": "Wrought Iron",
}

_MATERIAL_KEYWORDS: dict[str, str] = {
    "silk": "Silk",
    "cotton": "Cotton",
    "wool": "Wool",
    "brass": "Brass",
    "bell metal": "Bell Metal (Brass)",
    "iron": "Iron",
    "copper": "Copper",
    "teak": "Teak Wood",
    "wood": "Wood",
    "clay": "Clay",
    "enamel": "Enamel",
    "jute": "Jute",
}

_COLOR_KEYWORDS = [
    "red", "blue", "green", "yellow", "orange", "white", "black",
    "gold", "silver", "maroon", "pink", "purple", "indigo", "cream",
    "brown", "beige", "turquoise",
]


# ---------------------------------------------------------------------------
# Regex-based fallback parser
# ---------------------------------------------------------------------------

def _regex_extract(transcript: str) -> dict[str, Any]:
    """
    Rule-based extraction from plain English / transliterated Indic
    transcript.  Covers the 80 % happy path when Ollama is offline.
    """
    text = transcript.lower()

    # Craft type
    craft_type: Optional[str] = None
    for kw, ct in _CRAFT_KEYWORDS.items():
        if kw in text:
            craft_type = ct
            break

    # Material
    material: Optional[str] = None
    for kw, mat in _MATERIAL_KEYWORDS.items():
        if kw in text:
            material = mat
            break

    # Primary colour
    primary_color: Optional[str] = None
    for c in _COLOR_KEYWORDS:
        if c in text:
            primary_color = c.capitalize()
            break

    # Labor days - patterns like "5 days", "3 din", "in 7 days"
    labor_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:days?|din|dino)", text)
    labor_days: Optional[float] = float(labor_match.group(1)) if labor_match else None

    # Raw cost - patterns like "1200 rupees", "cost 800", "₹1500"
    cost_match = re.search(
        r"(?:cost|kharcha|lagat|₹|rs\.?|rupees?)\s*(?:of\s*)?(\d+(?:,\d+)*)",
        text,
    )
    if not cost_match:
        cost_match = re.search(
            r"(\d{3,})\s*(?:rupees?|rs|₹)", text
        )
    raw_cost: Optional[float] = None
    if cost_match:
        raw_cost = float(cost_match.group(1).replace(",", ""))

    # Build product noun for title
    product_noun = "Handcrafted Product"
    for kw in _CRAFT_KEYWORDS:
        if kw in text:
            product_noun = kw.replace("_", " ").title()
            break

    color_prefix = f"{primary_color} " if primary_color else ""
    material_prefix = f"{material} " if material else ""

    title_en = f"Handmade {color_prefix}{material_prefix}{product_noun}"
    title_hi = f"हस्तनिर्मित {product_noun}"

    desc_en = f"A {color_prefix.lower()}{material_prefix.lower()}{product_noun.lower()}"
    if labor_days:
        desc_en += f", handcrafted over {labor_days:.0f} days"
    if raw_cost:
        desc_en += f" with a material cost of ₹{raw_cost:.0f}"
    desc_en += "."

    desc_hi = f"एक {product_noun}"
    if labor_days:
        desc_hi += f", {labor_days:.0f} दिनों में हस्तनिर्मित"
    if raw_cost:
        desc_hi += f", कच्ची लागत ₹{raw_cost:.0f}"
    desc_hi += "।"

    return {
        "craft_type": craft_type,
        "material": material,
        "primary_color": primary_color,
        "labor_days": labor_days,
        "raw_cost": raw_cost,
        "title_en": title_en.strip(),
        "title_hi": title_hi.strip(),
        "description_en": desc_en.strip(),
        "description_hi": desc_hi.strip(),
    }


# ---------------------------------------------------------------------------
# Cloud LLM: Groq (Llama-3.3-70B / 8B)
# ---------------------------------------------------------------------------

async def _call_groq(transcript: str) -> Optional[dict[str, Any]]:
    """
    Call the Groq cloud LLM API using OpenAI-compatible format with JSON mode.
    Returns parsed dictionary or None on failure/missing key.
    """
    if not GROQ_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_PROMPT_TEMPLATE.format(transcript=transcript),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GROQ_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
            resp.raise_for_status()

        data = resp.json()
        raw_content = data["choices"][0]["message"]["content"]

        # Clean markdown wrappers if any
        raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content.strip())
        raw_content = re.sub(r"\s*```$", "", raw_content.strip())

        parsed = json.loads(raw_content)
        logger.info("Groq Cloud LLM (%s) successfully cataloged product.", GROQ_MODEL)
        return parsed

    except httpx.HTTPStatusError as exc:
        logger.warning("Groq API HTTP error %s: %s", exc.response.status_code, exc.response.text[:200])
    except Exception as exc:
        logger.warning("Groq API call failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Local LLM: Ollama call
# ---------------------------------------------------------------------------

async def _call_ollama(transcript: str) -> Optional[dict[str, Any]]:
    """
    Call the local Ollama instance and parse the JSON response.

    Returns ``None`` if the call fails or the response cannot be parsed.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_PROMPT_TEMPLATE.format(transcript=transcript),
            },
        ],
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=HTTP_TIMEOUT,
            )
            resp.raise_for_status()

        body = resp.json()
        raw_content: str = body.get("message", {}).get("content", "")

        # Strip markdown fences if present despite instructions
        raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content.strip())
        raw_content = re.sub(r"\s*```$", "", raw_content.strip())

        parsed = json.loads(raw_content)
        logger.info("Ollama (%s) returned structured catalog data.", OLLAMA_MODEL)
        return parsed

    except httpx.ConnectError:
        logger.warning("Ollama daemon unreachable at %s.", OLLAMA_BASE_URL)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Ollama HTTP %s: %s", exc.response.status_code, exc.response.text[:200]
        )
    except json.JSONDecodeError:
        logger.warning("Ollama response was not valid JSON - falling back to regex.")
    except Exception:
        logger.exception("Unexpected error calling Ollama.")

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def extract_and_translate_catalog(transcript: str) -> dict[str, Any]:
    """
    Extract structured product metadata from a free-form artisan transcript.

    Tries:
      1. Groq Cloud LLM (Llama-3.3-70B, high speed, production-ready)
      2. Local Ollama LLM (qwen2.5 / llama3)
      3. Rule-based regex parser (offline zero-dependency safety net)

    Parameters
    ----------
    transcript : str
        Plain-text transcript (English or Indic).

    Returns
    -------
    dict
        Keys: ``craft_type``, ``material``, ``primary_color``,
        ``labor_days``, ``raw_cost``, ``title_en``, ``title_hi``,
        ``description_en``, ``description_hi``.
    """
    if not transcript or not transcript.strip():
        logger.warning("Empty transcript supplied - returning empty catalog.")
        return {
            "craft_type": None,
            "material": None,
            "primary_color": None,
            "labor_days": None,
            "raw_cost": None,
            "title_en": "Untitled Product",
            "title_hi": "शीर्षकहीन उत्पाद",
            "description_en": "No description available.",
            "description_hi": "कोई विवरण उपलब्ध नहीं।",
        }

    # 1. Try Groq Cloud LLM first (fastest, production standard)
    llm_result = await _call_groq(transcript)

    # 2. Try local Ollama if Groq was not configured or failed
    if llm_result is None:
        llm_result = await _call_ollama(transcript)

    # If an LLM succeeded, validate required keys
    if llm_result is not None:
        for key in (
            "craft_type", "material", "primary_color", "labor_days",
            "raw_cost", "title_en", "title_hi", "description_en",
            "description_hi",
        ):
            llm_result.setdefault(key, None)
        return llm_result

    # 3. Final Fallback: regex parser
    logger.info("Using regex fallback cataloger.")
    return _regex_extract(transcript)
