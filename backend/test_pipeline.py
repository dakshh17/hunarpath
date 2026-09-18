"""
HunarPath — End-to-End Integration Test Pipeline.

Exercises every backend API endpoint programmatically with synthetic
payloads.  Designed to run either inside the Docker stack or against a
locally running backend (defaults to http://localhost:8000).

Usage
─────
    python test_pipeline.py                   # against localhost:8000
    python test_pipeline.py http://backend:8000  # inside Docker network

Exit code 0  = all assertions passed.
Exit code 1  = one or more assertions failed.
"""

from __future__ import annotations

import io
import json
import struct
import sys
import time
import wave

import httpx
import numpy as np

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TIMEOUT = 120.0  # generous for first-run rembg model download
PASS = "✅"
FAIL = "❌"
results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = ""):
    tag = PASS if passed else FAIL
    results.append((name, passed, detail))
    print(f"  {tag}  {name}" + (f"  ({detail})" if detail else ""))


# ── Synthetic payload generators ──────────────────────────────────────────────

def make_test_image_jpeg(width: int = 640, height: int = 480) -> bytes:
    """Generate a random-noise JPEG image as raw bytes."""
    from PIL import Image

    rng = np.random.default_rng(seed=123)
    arr = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf.read()


def make_test_wav(duration_secs: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate a valid mono 16-bit PCM WAV with a 440 Hz sine tone."""
    n_samples = int(sample_rate * duration_secs)
    t = np.linspace(0, duration_secs, n_samples, endpoint=False)
    tone = (np.sin(2 * np.pi * 440 * t) * 32767 * 0.5).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(tone.tobytes())
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════════════════════
# TEST CASES
# ══════════════════════════════════════════════════════════════════════════════


def test_healthcheck(client: httpx.Client):
    """T0: /healthz liveness probe."""
    r = client.get("/healthz", timeout=10)
    record("Healthcheck /healthz", r.status_code == 200, f"status={r.status_code}")


# ──────────────────────────────────────────────────────────────────────────────

def test_clusters_map(client: httpx.Client) -> list[dict]:
    """T1: GET /api/v1/clusters/map returns valid GeoJSON."""
    r = client.get("/api/v1/clusters/map", timeout=TIMEOUT)
    ok = r.status_code == 200
    record("Clusters map – HTTP 200", ok, f"status={r.status_code}")
    if not ok:
        return []

    body = r.json()
    features = body.get("features", [])
    record(
        "Clusters map – ≥ 3 features",
        len(features) >= 3,
        f"count={len(features)}",
    )
    record(
        "Clusters map – valid GeoJSON type",
        body.get("type") == "FeatureCollection",
    )

    # Verify each feature has required properties
    if features:
        props = features[0].get("properties", {})
        required_keys = {"id", "name", "state", "district", "primary_craft",
                         "combined_monthly_capacity", "active_artisan_count"}
        has_all = required_keys.issubset(props.keys())
        record("Clusters map – feature schema valid", has_all,
               f"keys={list(props.keys())[:6]}")

    return features


# ──────────────────────────────────────────────────────────────────────────────

def test_catalog_ingest(client: httpx.Client, artisan_id: str = "demo_artisan_001") -> dict | None:
    """T2: POST /api/v1/catalog/ingest with synthetic image + audio."""
    image_bytes = make_test_image_jpeg()
    audio_bytes = make_test_wav()

    files = {
        "image": ("test_product.jpg", image_bytes, "image/jpeg"),
        "audio": ("test_voice.wav", audio_bytes, "audio/wav"),
    }
    data = {"artisan_id": artisan_id, "language": "hi"}

    r = client.post("/api/v1/catalog/ingest", files=files, data=data, timeout=None)
    ok = r.status_code == 200
    record("Catalog ingest – HTTP 200", ok, f"status={r.status_code}")
    if not ok:
        print(f"    Response: {r.text[:300]}")
        return None

    body = r.json()

    # ── Structure assertions ──────────────────────────────────────────
    record(
        "Catalog ingest – has studio_image_base64",
        "studio_image_base64" in body and len(body["studio_image_base64"]) > 100,
    )
    record(
        "Catalog ingest – has raw_transcript",
        "raw_transcript" in body and len(body["raw_transcript"]) > 0,
    )
    record(
        "Catalog ingest – has catalog_metadata",
        "catalog_metadata" in body and isinstance(body["catalog_metadata"], dict),
    )
    record(
        "Catalog ingest – has price_recommendation",
        "price_recommendation" in body and isinstance(body["price_recommendation"], dict),
    )

    # ── Studio image has white background ─────────────────────────────
    import base64
    from PIL import Image

    try:
        img_bytes = base64.b64decode(body["studio_image_base64"])
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        # Sample four corners (should be white canvas — RGB ≥ 250)
        w, h = img.size
        corners = [
            img.getpixel((5, 5)),
            img.getpixel((w - 5, 5)),
            img.getpixel((5, h - 5)),
            img.getpixel((w - 5, h - 5)),
        ]
        all_white = all(
            val[0] >= 245 and val[1] >= 245 and val[2] >= 245 for val in corners
        )
        record(
            "Catalog ingest – studio image white background",
            all_white,
            f"corners={corners}",
        )
    except Exception as exc:
        record("Catalog ingest – studio image white background", False, str(exc))

    # ── Price > cost floor ────────────────────────────────────────────
    pricing = body.get("price_recommendation", {})
    cost_floor = pricing.get("cost_floor", 0)
    rec_price = pricing.get("recommended_price", 0)
    record(
        "Catalog ingest – price > cost floor",
        rec_price > cost_floor and cost_floor >= 0,
        f"recommended={rec_price}, floor={cost_floor}",
    )

    # ── Market corridor sanity ────────────────────────────────────────
    min_c = pricing.get("min_market_corridor", 0)
    max_c = pricing.get("max_market_corridor", 0)
    record(
        "Catalog ingest – corridor min < recommended < max",
        min_c <= rec_price <= max_c,
        f"[{min_c}, {rec_price}, {max_c}]",
    )

    return body


# ──────────────────────────────────────────────────────────────────────────────

def test_catalog_publish(client: httpx.Client, ingest_result: dict | None, artisan_id: str = "demo_artisan_001"):
    """T3: POST /api/v1/catalog/publish persists a product."""
    catalog = (ingest_result or {}).get("catalog_metadata", {})
    pricing = (ingest_result or {}).get("price_recommendation", {})

    payload = {
        "artisan_id": artisan_id,
        "title_en": catalog.get("title_en") or "Test Product",
        "title_hi": catalog.get("title_hi") or "टेस्ट उत्पाद",
        "craft_type": catalog.get("craft_type") or "Handloom Weaving",
        "material": catalog.get("material") or "Cotton",
        "raw_cost": catalog.get("raw_cost") or 500,
        "labor_days": catalog.get("labor_days") or 2,
        "recommended_price": pricing.get("recommended_price") or 1500,
        "min_market_corridor": pricing.get("min_market_corridor") or 1200,
        "max_market_corridor": pricing.get("max_market_corridor") or 2000,
        "is_active": True,
    }

    r = client.post("/api/v1/catalog/publish", json=payload, timeout=TIMEOUT)
    ok = r.status_code == 200
    record("Catalog publish – HTTP 200", ok, f"status={r.status_code}")
    if not ok:
        print(f"    Response: {r.text[:300]}")
        return

    body = r.json()
    record(
        "Catalog publish – product_id returned",
        "product_id" in body and len(body["product_id"]) > 0,
    )
    record(
        "Catalog publish – embedding stored",
        body.get("embedding_stored") is True,
    )
    record(
        "Catalog publish – success message",
        "success" in body.get("message", "").lower(),
    )


# ──────────────────────────────────────────────────────────────────────────────

def test_rfq_aggregate(client: httpx.Client, clusters: list[dict]):
    """T4: POST /api/v1/rfq/aggregate splits units across artisans."""
    if not clusters:
        record("RFQ aggregate – skipped (no clusters)", False, "no cluster data")
        return

    cluster_id = clusters[0]["properties"]["id"]

    payload = {
        "buyer_name": "Integration Test Buyer",
        "cluster_id": cluster_id,
        "target_units": 100,
        "target_unit_price": 1500.0,
        "custom_specs": "Automated integration test order",
    }

    r = client.post("/api/v1/rfq/aggregate", json=payload, timeout=TIMEOUT)
    ok = r.status_code == 200
    record("RFQ aggregate – HTTP 200", ok, f"status={r.status_code}")
    if not ok:
        print(f"    Response: {r.text[:300]}")
        return

    body = r.json()
    allocations = body.get("allocations", [])

    record(
        "RFQ aggregate – has rfq_id",
        "rfq_id" in body and len(body["rfq_id"]) > 0,
    )
    record(
        "RFQ aggregate – status is ALLOCATED",
        body.get("status") == "ALLOCATED",
    )
    record(
        "RFQ aggregate – multiple artisan allocations",
        len(allocations) >= 2,
        f"artisan_count={len(allocations)}",
    )

    # Units sum to target
    total_allocated = sum(a["allocated_units"] for a in allocations)
    record(
        "RFQ aggregate – allocated units sum = target",
        total_allocated == 100,
        f"sum={total_allocated}",
    )

    # Each artisan has > 0 units
    all_positive = all(a["allocated_units"] > 0 for a in allocations)
    record(
        "RFQ aggregate – every artisan gets > 0 units",
        all_positive,
    )

    # Total value matches
    expected_value = 100 * 1500.0
    record(
        "RFQ aggregate – total_value = units × price",
        body.get("total_value") == expected_value,
        f"total_value={body.get('total_value')}",
    )
    
    return allocations


# ──────────────────────────────────────────────────────────────────────────────

def test_demand_radar(client: httpx.Client):
    """T5: GET /api/v1/demand-radar returns trend alerts."""
    r = client.get(
        "/api/v1/demand-radar",
        params={"dialect": "en", "limit": 5},
        timeout=TIMEOUT,
    )
    ok = r.status_code == 200
    record("Demand radar – HTTP 200", ok, f"status={r.status_code}")
    if not ok:
        return

    body = r.json()
    alerts = body.get("alerts", [])

    record(
        "Demand radar – has alerts",
        len(alerts) >= 1,
        f"count={len(alerts)}",
    )

    if alerts:
        a = alerts[0]
        required = {"craft_category", "region", "search_count", "pct_change", "notification"}
        has_keys = required.issubset(a.keys())
        record("Demand radar – alert schema valid", has_keys)

        record(
            "Demand radar – notification is non-empty",
            len(a.get("notification", "")) > 10,
        )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{'═' * 64}")
    print(f"  HunarPath Integration Test Suite")
    print(f"  Target: {BASE_URL}")
    print(f"{'═' * 64}\n")

    # ── Wait for backend readiness ────────────────────────────────────
    print("⏳ Waiting for backend to become healthy …")
    client = httpx.Client(base_url=BASE_URL, follow_redirects=True)

    for attempt in range(30):
        try:
            r = client.get("/healthz", timeout=5)
            if r.status_code == 200:
                print(f"   Backend ready (attempt {attempt + 1})\n")
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(2)
    else:
        print("   ❌ Backend did not become healthy in 60 s — aborting.\n")
        sys.exit(1)

    # ── Run test suites ───────────────────────────────────────────────

    print("─── T0: Healthcheck ────────────────────────────────────────")
    test_healthcheck(client)

    print("\n─── T1: Clusters Map ───────────────────────────────────────")
    clusters = test_clusters_map(client)

    print("\n─── T4: RFQ Aggregate ──────────────────────────────────────")
    allocations = test_rfq_aggregate(client, clusters)
    
    artisan_id = "demo_artisan_001"
    if allocations:
        artisan_id = allocations[0].get("artisan_id", artisan_id)

    print("\n─── T2: Catalog Ingest Pipeline ─────────────────────────────")
    ingest_result = test_catalog_ingest(client, artisan_id=artisan_id)

    print("\n─── T3: Catalog Publish ────────────────────────────────────")
    test_catalog_publish(client, ingest_result, artisan_id=artisan_id)

    print("\n─── T5: Demand Radar ───────────────────────────────────────")
    test_demand_radar(client)

    client.close()

    # ── Summary ───────────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed

    print(f"\n{'═' * 64}")
    print(f"  Results:  {passed}/{total} passed")
    if failed:
        print(f"  FAILURES:")
        for name, ok, detail in results:
            if not ok:
                print(f"    {FAIL}  {name}  {detail}")
    print(f"{'═' * 64}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
