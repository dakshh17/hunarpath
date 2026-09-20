"""
HunarPath AI service layer.

Modules
-------
- vision_service     - Background removal, CLAHE, studio compositing.
- bhashini_service   - Indic ASR via Bhashini ULCA pipeline.
- cataloger_service  - LLM-based structured extraction (Ollama + regex fallback).
- pricing_service    - Cost-plus dynamic pricing with XGBoost / heuristic.
- demand_radar       - Search-trend aggregation and dialect notifications.
"""

from .vision_service import process_studio_image
from .bhashini_service import transcribe_indic_audio
from .cataloger_service import extract_and_translate_catalog
from .pricing_service import calculate_price_recommendation
from .demand_radar import generate_demand_alerts, get_top_trends

__all__ = [
    "process_studio_image",
    "transcribe_indic_audio",
    "extract_and_translate_catalog",
    "calculate_price_recommendation",
    "generate_demand_alerts",
    "get_top_trends",
]
