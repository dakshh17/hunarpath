"""
ShilpSetu – Dynamic Pricing Assistant.

Computes a fair recommended retail price for handcrafted products using
a cost-plus methodology augmented by:

  • Craft rarity index (higher for rare / time-intensive crafts).
  • Seasonal demand multiplier.
  • XGBoost regressor (when a trained model is available on disk).
  • Calibrated heuristic fallback (always available).

The artisan's net margin is calculated after subtracting raw material
cost and a nominal platform / logistics fee.
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DAILY_WAGE_RATE: float = float(os.getenv("DAILY_WAGE_RATE", "350.0"))
SEASONAL_MULTIPLIER: float = float(os.getenv("SEASONAL_MULTIPLIER", "1.15"))
PLATFORM_FEE_RATIO: float = float(os.getenv("PLATFORM_FEE_RATIO", "0.10"))

MODEL_PATH: Path = Path(
    os.getenv("PRICING_MODEL_PATH", "models/xgb_pricing.pkl")
)

# Craft rarity index – higher values indicate rarer / more prestigious crafts
CRAFT_RARITY_INDEX: dict[str, float] = {
    "Zari & Brocade": 1.45,
    "Meenakari": 1.40,
    "Bell Metal Craft": 1.35,
    "Handloom Weaving": 1.25,
    "Block Printing": 1.20,
    "Mirror Work": 1.20,
    "Embroidery": 1.15,
    "Wood Carving": 1.30,
    "Wrought Iron": 1.10,
    "Terracotta": 1.05,
}

DEFAULT_RARITY: float = 1.15

# Market corridor bounds relative to recommended price
CORRIDOR_LOW_RATIO: float = 0.80
CORRIDOR_HIGH_RATIO: float = 1.30

# ---------------------------------------------------------------------------
# XGBoost model loader (lazy singleton)
# ---------------------------------------------------------------------------
_xgb_model: Optional[object] = None  # xgboost.XGBRegressor or None
_xgb_load_attempted: bool = False


def _try_load_xgb():
    """
    Attempt to load a pre-trained XGBoost pricing model from disk.

    The model is expected to accept a feature vector:
        [raw_cost, labor_cost, rarity_index, seasonal_multiplier]
    and predict the recommended retail price.
    """
    global _xgb_model, _xgb_load_attempted
    _xgb_load_attempted = True

    if not MODEL_PATH.exists():
        logger.info(
            "No XGBoost pricing model found at '%s' – using heuristic.", MODEL_PATH
        )
        return

    try:
        with open(MODEL_PATH, "rb") as fh:
            _xgb_model = pickle.load(fh)
        logger.info("Loaded XGBoost pricing model from '%s'.", MODEL_PATH)
    except Exception:
        logger.exception("Failed to load XGBoost model – falling back to heuristic.")
        _xgb_model = None


# ---------------------------------------------------------------------------
# Internal pricing strategies
# ---------------------------------------------------------------------------

def _heuristic_price(
    raw_cost: float,
    labor_cost: float,
    rarity: float,
    seasonal: float,
) -> float:
    """
    Calibrated heuristic:

        recommended = (raw_cost + labor_cost) × rarity × seasonal × margin_factor

    The margin_factor of 1.6 targets a ~35–40 % artisan margin after
    platform fees.
    """
    margin_factor = 1.60
    return round((raw_cost + labor_cost) * rarity * seasonal * margin_factor, 2)


def _xgb_price(
    raw_cost: float,
    labor_cost: float,
    rarity: float,
    seasonal: float,
) -> Optional[float]:
    """Predict price using the XGBoost regressor, if loaded."""
    if not _xgb_load_attempted:
        _try_load_xgb()

    if _xgb_model is None:
        return None

    try:
        features = np.array([[raw_cost, labor_cost, rarity, seasonal]])
        prediction = float(_xgb_model.predict(features)[0])
        return round(max(prediction, raw_cost + labor_cost), 2)
    except Exception:
        logger.exception("XGBoost prediction failed – using heuristic fallback.")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_price_recommendation(
    raw_cost: float,
    labor_days: float,
    craft_type: str,
    cluster_id: Optional[str] = None,
) -> dict:
    """
    Compute a fair pricing recommendation for a handcraft product.

    Parameters
    ----------
    raw_cost : float
        Total raw-material cost (₹).
    labor_days : float
        Number of artisan labor days.
    craft_type : str
        Craft category string (matched against rarity index).
    cluster_id : str, optional
        Cluster identifier (reserved for future cluster-level adjustments).

    Returns
    -------
    dict
        ``cost_floor``            – absolute minimum viable price.
        ``recommended_price``     – AI/heuristic suggested retail price.
        ``min_market_corridor``   – lower bound of the fair-trade corridor.
        ``max_market_corridor``   – upper bound of the fair-trade corridor.
        ``net_artisan_margin``    – estimated artisan take-home after fees.
        ``pricing_method``        – ``"xgboost"`` or ``"heuristic"``.
    """
    labor_cost = labor_days * DAILY_WAGE_RATE
    cost_floor = round(raw_cost + labor_cost, 2)

    rarity = CRAFT_RARITY_INDEX.get(craft_type, DEFAULT_RARITY)

    # Try XGBoost first, fall back to heuristic
    xgb_pred = _xgb_price(raw_cost, labor_cost, rarity, SEASONAL_MULTIPLIER)
    if xgb_pred is not None:
        recommended = xgb_pred
        method = "xgboost"
    else:
        recommended = _heuristic_price(
            raw_cost, labor_cost, rarity, SEASONAL_MULTIPLIER
        )
        method = "heuristic"

    # Ensure recommended is never below cost floor
    recommended = max(recommended, cost_floor * 1.25)

    min_corridor = round(recommended * CORRIDOR_LOW_RATIO, 2)
    max_corridor = round(recommended * CORRIDOR_HIGH_RATIO, 2)

    # Net artisan margin = recommended - raw_cost - platform fee
    platform_fee = round(recommended * PLATFORM_FEE_RATIO, 2)
    net_margin = round(recommended - raw_cost - platform_fee, 2)

    return {
        "cost_floor": cost_floor,
        "recommended_price": round(recommended, 2),
        "min_market_corridor": min_corridor,
        "max_market_corridor": max_corridor,
        "net_artisan_margin": net_margin,
        "pricing_method": method,
    }
