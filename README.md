# HunarPath AI - SIH 26090

> AI-powered bridge connecting India's heritage artisan clusters with global
> buyers. Fair pricing, studio-quality cataloging, and transparent supply
> chains - all from a single voice note.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         docker compose up                          │
│                                                                     │
│  ┌──────────┐      ┌──────────────────┐      ┌──────────────────┐  │
│  │   db      │◄────►│    backend       │◄────►│      web         │  │
│  │ pgvector  │      │  FastAPI + AI    │      │ Next.js 14       │  │
│  │ :5432     │      │  :8000           │      │ :3000            │  │
│  └──────────┘      └──────────────────┘      └──────────────────┘  │
│                           ▲                                         │
│                           │  HTTP                                   │
│                    ┌──────┴──────┐                                  │
│                    │ artisan_    │                                   │
│                    │ mobile      │                                   │
│                    │ (Flutter)   │                                   │
│                    └─────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
```

| Service          | Tech Stack                                         | Port   |
|------------------|----------------------------------------------------|--------|
| **db**           | PostgreSQL 16 + pgvector                           | `5432` |
| **backend**      | Python 3.11 · FastAPI · SQLAlchemy 2 · rembg · XGBoost | `8000` |
| **web**          | Next.js 14 (App Router) · Tailwind CSS · Leaflet   | `3000` |
| **artisan_mobile** | Flutter · Provider · flutter_tts · record        | -      |

---

## Quickstart

### Prerequisites

| Tool     | Minimum Version |
|----------|-----------------|
| Docker   | 24.x            |
| Docker Compose | v2.20+    |
| Git      | 2.x             |

### 1 - Clone & Launch

```bash
git clone <repo-url> && cd hunarpath

# Build and start all three containers
docker compose up --build
```

> **First run** takes 3-5 minutes (Python deps, Next.js build, pgvector
> extension install).  Subsequent starts are near-instant.

### 2 - Verify Database Seed

The backend auto-seeds mock data on startup (3 clusters, 10 artisans,
15 products, 5 search trends).  Confirm in logs:

```bash
docker compose logs backend | grep -i "seed"
# Expected: "Mock data seed completed."
```

Or query directly:

```bash
docker compose exec db psql -U hunarpath -c "SELECT name, district FROM clusters;"
```

Expected output:

| name                        | district  |
|-----------------------------|-----------|
| Kachchh Weaving Cluster     | Kachchh   |
| Varanasi Zari Cluster       | Varanasi  |
| Bastar Bell Metal Cluster   | Bastar    |

### 3 - Verify Endpoints

```bash
# Health check
curl http://localhost:8000/healthz

# Cluster map (GeoJSON)
curl http://localhost:8000/api/v1/clusters/map | python -m json.tool

# Demand radar
curl "http://localhost:8000/api/v1/demand-radar?dialect=en&limit=3"
```

### 4 - Run Integration Tests

```bash
# Inside the backend container
docker compose exec backend python test_pipeline.py

# Or against a local backend (without Docker)
cd backend && python test_pipeline.py http://localhost:8000
```

Expected output:

```
═══════════════════════════════════════════════════════════════
  HunarPath Integration Test Suite
  Target: http://localhost:8000
═══════════════════════════════════════════════════════════════

─── T0: Healthcheck ───────────────────────────────────────
    Healthcheck /healthz

─── T1: Clusters Map ──────────────────────────────────────
    Clusters map - HTTP 200
    Clusters map - ≥ 3 features
    Clusters map - valid GeoJSON type
    Clusters map - feature schema valid

─── T2: Catalog Ingest Pipeline ───────────────────────────
    Catalog ingest - HTTP 200
    Catalog ingest - has studio_image_base64
    Catalog ingest - has raw_transcript
    Catalog ingest - has catalog_metadata
    Catalog ingest - has price_recommendation
    Catalog ingest - studio image white background
    Catalog ingest - price > cost floor
    Catalog ingest - corridor min < recommended < max

─── T3: Catalog Publish ───────────────────────────────────
    Catalog publish - HTTP 200
    Catalog publish - product_id returned
    Catalog publish - embedding stored
    Catalog publish - success message

─── T4: RFQ Aggregate ────────────────────────────────────
    RFQ aggregate - HTTP 200
    RFQ aggregate - has rfq_id
    RFQ aggregate - status is ALLOCATED
    RFQ aggregate - multiple artisan allocations
    RFQ aggregate - allocated units sum = target
    RFQ aggregate - every artisan gets > 0 units
    RFQ aggregate - total_value = units × price

─── T5: Demand Radar ─────────────────────────────────────
    Demand radar - HTTP 200
    Demand radar - has alerts
    Demand radar - alert schema valid
    Demand radar - notification is non-empty

═══════════════════════════════════════════════════════════════
  Results:  25/25 passed
═══════════════════════════════════════════════════════════════
```

---

## API Reference

| Method | Endpoint                     | Description                              |
|--------|------------------------------|------------------------------------------|
| `GET`  | `/healthz`                   | Liveness probe                           |
| `GET`  | `/api/v1/clusters/map`       | GeoJSON FeatureCollection of clusters    |
| `POST` | `/api/v1/catalog/ingest`     | Image + audio → studio photo + catalog   |
| `POST` | `/api/v1/catalog/publish`    | Persist approved product + embedding     |
| `POST` | `/api/v1/rfq/aggregate`      | Buyer RFQ → artisan allocation ledger    |
| `GET`  | `/api/v1/demand-radar`       | Search trend alerts (dialect-localised)  |

Full interactive docs: **http://localhost:8000/docs** (Swagger UI)

---

## Local Development (Without Docker)

### Backend

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -r requirements.txt

# Starts with SQLite fallback (no Postgres needed)
python mock_data.py          # seed local DB
uvicorn main:app --reload    # http://localhost:8000
```

### Web

```bash
cd web
npm install
npm run dev                  # http://localhost:3000
```

### Mobile

```bash
cd artisan_mobile
flutter pub get
flutter run                  # launch on connected device / emulator
```

---

## Project Structure

```
hunarpath/
├── docker-compose.yml              ← orchestrates db + backend + web
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                     ← FastAPI gateway (5 endpoints)
│   ├── database.py                 ← async SQLAlchemy + pgvector
│   ├── models.py                   ← ORM (clusters, artisans, products, rfqs, search_trends)
│   ├── schemas.py                  ← Pydantic v2 request/response models
│   ├── mock_data.py                ← seed 3 clusters, 10 artisans, 15 products
│   ├── test_pipeline.py            ← 25-assertion E2E integration test
│   └── services/
│       ├── vision_service.py       ← rembg + CLAHE + drop-shadow + white canvas
│       ├── bhashini_service.py     ← Indic ASR (Bhashini ULCA + offline fallback)
│       ├── cataloger_service.py    ← Ollama LLM extraction + regex fallback
│       ├── pricing_service.py      ← XGBoost / heuristic dynamic pricing
│       └── demand_radar.py         ← search trend aggregation + dialect alerts
│
├── web/
│   ├── Dockerfile
│   ├── package.json
│   └── src/app/
│       ├── map/page.tsx            ← Leaflet cluster map
│       ├── catalog/page.tsx        ← semantic search marketplace
│       ├── rfq/page.tsx            ← bulk order + allocation engine
│       └── demand-radar/page.tsx   ← trend bar chart + regional cards
│
└── artisan_mobile/
    ├── pubspec.yaml
    └── lib/
        ├── screens/                ← home, capture, review, orders
        ├── services/               ← api_client, audio_feedback
        ├── providers/              ← artisan_provider (ChangeNotifier)
        └── theme/                  ← high-contrast tactile theme
```

---

## Team

**Smart India Hackathon 2024 - Problem Statement SIH26090**

Built with ️ for India's 7 million+ artisans.
