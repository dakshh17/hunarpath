"""
HunarPath - XGBoost Fair-Trade Pricing Model Trainer.

Generates a synthetic dataset of 5,000 Indian handicraft pricing records
across all 10 craft categories, trains an XGBRegressor, evaluates it,
and serializes the model to ``models/xgb_pricing.pkl``.

Feature vector (4 features):
    [raw_cost, labor_cost, rarity_index, seasonal_multiplier]

Target:
    recommended_price  (₹)

Usage
-----
    python train_pricing_model.py
"""

from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from xgboost import XGBRegressor

# ---------------------------------------------------------------------------
# Constants (mirroring pricing_service.py)
# ---------------------------------------------------------------------------

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

# Realistic raw material cost ranges (₹) per craft
CRAFT_COST_RANGES: dict[str, tuple[float, float]] = {
    "Zari & Brocade": (800, 8000),
    "Meenakari": (600, 5000),
    "Bell Metal Craft": (400, 3500),
    "Handloom Weaving": (200, 4000),
    "Block Printing": (100, 2000),
    "Mirror Work": (150, 2500),
    "Embroidery": (100, 1800),
    "Wood Carving": (300, 3000),
    "Wrought Iron": (200, 2500),
    "Terracotta": (50, 800),
}

# Labor-day ranges per craft
CRAFT_LABOR_RANGES: dict[str, tuple[float, float]] = {
    "Zari & Brocade": (3, 30),
    "Meenakari": (2, 25),
    "Bell Metal Craft": (2, 20),
    "Handloom Weaving": (2, 25),
    "Block Printing": (1, 10),
    "Mirror Work": (1, 12),
    "Embroidery": (1, 15),
    "Wood Carving": (2, 18),
    "Wrought Iron": (1, 10),
    "Terracotta": (0.5, 5),
}

DAILY_WAGE_RATE = 350.0
RECORDS_PER_CRAFT = 500  # 500 × 10 crafts = 5,000 records
RANDOM_SEED = 42

MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "xgb_pricing.pkl"


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def _ground_truth_price(
    raw_cost: float,
    labor_cost: float,
    rarity: float,
    seasonal: float,
    rng: np.random.Generator,
) -> float:
    """
    Non-linear ground-truth pricing formula that captures real-world
    fair-trade pricing dynamics:

        base     = (raw_cost + labor_cost) × rarity × seasonal
        premium  = base × craftsmanship_premium(labor_cost)
        noise    = ±5 % Gaussian jitter (market variation)

    The craftsmanship premium rewards high-labor items with a convex
    scaling factor, reflecting the reality that artisan skill-intensive
    products command disproportionately higher prices.
    """
    base = (raw_cost + labor_cost) * rarity * seasonal

    # Convex craftsmanship premium: higher labor → steeper markup
    craftsmanship = 1.0 + 0.15 * np.log1p(labor_cost / 1000.0)

    # Heritage premium: rare crafts get extra lift
    heritage = 1.0 + 0.10 * (rarity - 1.0)

    price = base * craftsmanship * heritage * 1.60  # 1.60 is the margin factor
    price *= (1.0 + rng.normal(0.0, 0.05))          # ±5 % market noise

    return max(price, raw_cost + labor_cost)


def generate_dataset(
    n_per_craft: int = RECORDS_PER_CRAFT,
    seed: int = RANDOM_SEED,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic handicraft pricing data.

    Returns
    -------
    X : np.ndarray, shape (N, 4)
        Feature matrix: [raw_cost, labor_cost, rarity_index, seasonal_multiplier].
    y : np.ndarray, shape (N,)
        Target: recommended price (₹).
    """
    rng = np.random.default_rng(seed)
    rows_X: list[list[float]] = []
    rows_y: list[float] = []

    for craft, rarity in CRAFT_RARITY_INDEX.items():
        cost_lo, cost_hi = CRAFT_COST_RANGES[craft]
        labor_lo, labor_hi = CRAFT_LABOR_RANGES[craft]

        for _ in range(n_per_craft):
            raw_cost = rng.uniform(cost_lo, cost_hi)
            labor_days = rng.uniform(labor_lo, labor_hi)
            labor_cost = labor_days * DAILY_WAGE_RATE
            seasonal = rng.choice([1.0, 1.05, 1.10, 1.15, 1.20, 1.25])

            price = _ground_truth_price(raw_cost, labor_cost, rarity, seasonal, rng)

            rows_X.append([raw_cost, labor_cost, rarity, seasonal])
            rows_y.append(round(price, 2))

    X = np.array(rows_X, dtype=np.float32)
    y = np.array(rows_y, dtype=np.float32)
    return X, y


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_and_save() -> None:
    """Train the XGBRegressor and save to disk."""
    print("=" * 60)
    print("  HunarPath - XGBoost Pricing Model Trainer")
    print("=" * 60)

    # 1. Generate data
    print("\n[1/4] Generating 5,000 synthetic handicraft records ...")
    X, y = generate_dataset()
    print(f"      Dataset shape: X={X.shape}, y={y.shape}")
    print(f"      Price range : ₹{y.min():.0f} - ₹{y.max():.0f}")
    print(f"      Mean price  : ₹{y.mean():.0f}")

    # 2. Train/test split
    print("\n[2/4] Splitting into train (80 %) / test (20 %) ...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_SEED
    )
    print(f"      Train: {X_train.shape[0]} samples")
    print(f"      Test : {X_test.shape[0]} samples")

    # 3. Train XGBRegressor
    print("\n[3/4] Training XGBRegressor ...")
    model = XGBRegressor(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.9,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=RANDOM_SEED,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(X_train, y_train)

    # 4. Evaluate
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)

    print(f"\n[4/4] Evaluation on test set:")
    print(f"      R² Score : {r2:.4f}")
    print(f"      MAE      : ₹{mae:.2f}")

    if r2 < 0.96:
        print(f"\n️  WARNING: R² = {r2:.4f} is below the target of 0.96.")
        print("    The model will still be saved, but consider tuning hyperparams.")
    else:
        print(f"\n  R² = {r2:.4f} meets the target (> 0.96). Model is production-ready.")

    # Feature importance
    importance = model.feature_importances_
    feature_names = ["raw_cost", "labor_cost", "rarity_index", "seasonal_multiplier"]
    print("\n   Feature Importance:")
    for name, imp in sorted(zip(feature_names, importance), key=lambda x: -x[1]):
        bar = "█" * int(imp * 40)
        print(f"      {name:25s} {imp:.3f}  {bar}")

    # 5. Save model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as fh:
        pickle.dump(model, fh)
    size_kb = MODEL_PATH.stat().st_size / 1024
    print(f"\n  Model saved to: {MODEL_PATH}  ({size_kb:.1f} KB)")

    # 6. Quick sanity check
    print("\n--- Sanity Check ---")
    test_cases = [
        ("Terracotta (simple)", 200, 1, "Terracotta", 1.0),
        ("Block Print (mid)", 800, 4, "Block Printing", 1.15),
        ("Zari Brocade (premium)", 5000, 20, "Zari & Brocade", 1.20),
    ]
    for label, raw_cost, labor_days, craft, seasonal in test_cases:
        labor_cost = labor_days * DAILY_WAGE_RATE
        rarity = CRAFT_RARITY_INDEX[craft]
        features = np.array([[raw_cost, labor_cost, rarity, seasonal]], dtype=np.float32)
        pred = model.predict(features)[0]
        cost_floor = raw_cost + labor_cost
        margin_pct = ((pred - raw_cost) / pred) * 100
        print(f"   {label:30s}  Cost: ₹{cost_floor:>8,.0f}  →  Predicted: ₹{pred:>10,.0f}  (margin: {margin_pct:.0f}%)")

    print("\n" + "=" * 60)
    print("  Training complete!")
    print("=" * 60)


if __name__ == "__main__":
    train_and_save()
