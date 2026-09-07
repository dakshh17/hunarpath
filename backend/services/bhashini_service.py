"""
ShilpSetu – Indic Speech Engine (Bhashini ULCA ASR).

Provides Indic-language speech-to-text using the government Bhashini
ULCA pipeline.  Falls back to an offline heuristic transcript when the
API key is missing or the upstream service is unreachable.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BHASHINI_API_KEY: Optional[str] = os.getenv("BHASHINI_API_KEY")
BHASHINI_USER_ID: Optional[str] = os.getenv("BHASHINI_USER_ID")

# Meity / Bhashini ULCA endpoints
BHASHINI_PIPELINE_URL: str = os.getenv(
    "BHASHINI_PIPELINE_URL",
    "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline",
)
BHASHINI_COMPUTE_URL: str = os.getenv(
    "BHASHINI_COMPUTE_URL",
    "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
)
BHASHINI_INFERENCE_KEY: Optional[str] = os.getenv("BHASHINI_INFERENCE_KEY")

# Supported language codes (ISO 639-1 / ULCA)
SUPPORTED_LANGS = {"hi", "gu", "bn", "ta", "te", "mr", "kn", "ml", "pa", "or", "en"}

HTTP_TIMEOUT: float = 30.0  # seconds

# ---------------------------------------------------------------------------
# Offline fallback transcripts keyed by (lang_code, keyword hint)
# ---------------------------------------------------------------------------
_FALLBACK_TRANSCRIPTS: dict[str, str] = {
    "hi": (
        "यह एक हस्तनिर्मित लाल ज़री सिल्क साड़ी है जो 5 दिनों में "
        "बनाई गई है और इसकी कच्ची लागत 1200 रुपये है"
    ),
    "gu": (
        "આ હાથવણાટનો લાલ પટોળા દુપટ્ટો છે જે 4 દિવસમાં બનાવવામાં "
        "આવ્યો છે અને તેની કાચી કિંમત 800 રૂપિયા છે"
    ),
    "bn": (
        "এটি একটি হাতে তৈরি লাল জরি সিল্কের শাড়ি যা ৫ দিনে "
        "তৈরি হয়েছে এবং কাঁচামালের খরচ ১২০০ টাকা"
    ),
    "en": (
        "This is a handmade red zari silk saree made in 5 days "
        "with raw cost of 1200 rupees"
    ),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _resolve_asr_service_id(
    lang_code: str, client: httpx.AsyncClient
) -> tuple[str, str, str]:
    """
    Call the Bhashini pipeline config endpoint to resolve the ASR
    service ID and callback URL for the given language.

    Returns (service_id, callback_url, inference_api_key).
    """
    payload = {
        "pipelineTasks": [{"taskType": "asr", "config": {"language": {"sourceLanguage": lang_code}}}],
        "pipelineRequestConfig": {"pipelineId": "64392f96daac500b55c543cd"},
    }
    headers = {
        "Content-Type": "application/json",
        "userID": BHASHINI_USER_ID or "",
        "ulcaApiKey": BHASHINI_API_KEY or "",
    }
    resp = await client.post(
        BHASHINI_PIPELINE_URL, json=payload, headers=headers, timeout=HTTP_TIMEOUT
    )
    resp.raise_for_status()
    data = resp.json()

    pipeline_cfg = data["pipelineResponseConfig"][0]["config"][0]
    service_id = pipeline_cfg["serviceId"]
    callback_url = data.get("pipelineInferenceAPIEndPoint", {}).get(
        "callbackUrl", BHASHINI_COMPUTE_URL
    )
    inference_key = (
        data.get("pipelineInferenceAPIEndPoint", {})
        .get("inferenceApiKey", {})
        .get("value", BHASHINI_INFERENCE_KEY or "")
    )
    return service_id, callback_url, inference_key


async def _call_asr(
    audio_b64: str,
    lang_code: str,
    service_id: str,
    callback_url: str,
    inference_key: str,
    client: httpx.AsyncClient,
) -> str:
    """Send base64-encoded audio to the Bhashini ASR compute endpoint."""
    payload = {
        "pipelineTasks": [
            {
                "taskType": "asr",
                "config": {
                    "language": {"sourceLanguage": lang_code},
                    "serviceId": service_id,
                    "audioFormat": "wav",
                    "samplingRate": 16000,
                },
            }
        ],
        "inputData": {
            "audio": [{"audioContent": audio_b64}],
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": inference_key,
    }
    resp = await client.post(
        callback_url, json=payload, headers=headers, timeout=HTTP_TIMEOUT
    )
    resp.raise_for_status()
    result = resp.json()

    transcript = (
        result.get("pipelineResponse", [{}])[0]
        .get("output", [{}])[0]
        .get("source", "")
    )
    return transcript.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def transcribe_indic_audio(
    audio_bytes: bytes,
    lang_code: str = "hi",
) -> str:
    """
    Transcribe Indic-language audio to text.

    Parameters
    ----------
    audio_bytes : bytes
        Raw audio data (WAV / MP3 / OGG).
    lang_code : str
        ISO 639-1 code – ``hi``, ``gu``, ``bn``, etc.

    Returns
    -------
    str
        Plain-text transcript.

    Notes
    -----
    Falls back to an offline sample transcript when:
    - ``BHASHINI_API_KEY`` is not set in the environment, or
    - the upstream Bhashini service is unreachable / returns an error.
    """
    lang_code = lang_code.strip().lower()
    if lang_code not in SUPPORTED_LANGS:
        logger.warning(
            "Unsupported language code '%s' – defaulting to 'hi'.", lang_code
        )
        lang_code = "hi"

    # ── Fast-path: no API key → immediate offline fallback ────────────
    if not BHASHINI_API_KEY:
        logger.info(
            "BHASHINI_API_KEY not set – returning offline fallback transcript "
            "for lang='%s'.",
            lang_code,
        )
        return _FALLBACK_TRANSCRIPTS.get(lang_code, _FALLBACK_TRANSCRIPTS["en"])

    # ── Online path ───────────────────────────────────────────────────
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

    try:
        async with httpx.AsyncClient() as client:
            service_id, callback_url, inference_key = (
                await _resolve_asr_service_id(lang_code, client)
            )
            transcript = await _call_asr(
                audio_b64, lang_code, service_id, callback_url, inference_key, client
            )
            if transcript:
                logger.info("Bhashini ASR returned %d-char transcript.", len(transcript))
                return transcript
            else:
                logger.warning("Bhashini ASR returned empty transcript – using fallback.")

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Bhashini ASR HTTP error %s: %s – falling back to offline.",
            exc.response.status_code,
            exc.response.text[:200],
        )
    except httpx.ConnectError:
        logger.error("Bhashini ASR connection refused – falling back to offline.")
    except Exception:
        logger.exception("Unexpected Bhashini ASR failure – falling back to offline.")

    return _FALLBACK_TRANSCRIPTS.get(lang_code, _FALLBACK_TRANSCRIPTS["en"])
