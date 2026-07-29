# AI-Powered Restaurant Recommendation System

An AI-powered restaurant recommendation service inspired by Zomato. The system combines structured restaurant data with an LLM to produce personalized recommendations.

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1 — Data Layer | **Complete** | Load, preprocess, and query restaurant data |
| 2 — Input & Filtering | **Complete** | User preference validation and candidate filtering |
| 3 — LLM Integration | **Complete** | Prompt design and LLM API client |
| 4 — Recommendation Engine | **Complete** | Rank, explain, and validate recommendations |
| 5 — Output & UI | **Complete** | User-facing interface |

## Phase 1: Data Layer

Loads the [Zomato dataset from Hugging Face](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation), preprocesses it, and exposes a queryable `RestaurantRepository`.

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### Verify data load

```bash
python scripts/load_data.py --location Bangalore --top 5
```

Optional quick test with a row limit:

```bash
python scripts/load_data.py --max-rows 500 --location Bangalore
```

### Run tests

Unit tests (no network required):

```bash
pytest tests/test_data.py -m "not integration"
```

Full suite including Hugging Face integration:

```bash
pytest tests/test_data.py
```

### Project structure

```
src/data/
├── config.py         # Dataset name, budget thresholds, location aliases
├── models.py         # Restaurant, FilterCriteria, Budget
├── loader.py         # Hugging Face loader with retry
├── preprocessor.py   # Clean and normalize raw rows
├── repository.py     # RestaurantRepository
└── exceptions.py     # Data layer errors
```

### Usage

```python
from src.data.models import Budget, FilterCriteria
from src.data.repository import RestaurantRepository

repo = RestaurantRepository()
repo.load()

# Filter by city, cuisine, rating, and budget
results = repo.filter_by(
    FilterCriteria(
        location="Bangalore",
        cuisine="Italian",
        min_rating=4.0,
        budget=Budget.MEDIUM,
    )
)

for r in results[:5]:
    print(r.name, r.rating, r.cost_display)
```

## Phase 2: Input & Filtering

Validates user preferences and returns a bounded, ranked candidate list ready for LLM processing (Phase 3).

### Verify filtering

```bash
python scripts/filter_candidates.py --location Bangalore --budget medium --cuisine Italian --min-rating 4.0
```

### Run tests

```bash
pytest tests/test_filter.py -m "not integration" -v
pytest tests/test_filter.py -v   # includes Hugging Face integration
```

### Project structure

```
src/input/
├── config.py         # MAX_CANDIDATES, field limits
├── schemas.py        # UserPreference, FilterResult
├── validator.py      # validate_preferences()
├── filter_engine.py  # FilterEngine
└── exceptions.py     # InputValidationError
```

### Usage

```python
from src.data.repository import RestaurantRepository
from src.input import FilterEngine, validate_preferences

repo = RestaurantRepository()
repo.load()

prefs = validate_preferences({
    "location": "Bangalore",
    "budget": "medium",
    "cuisine": "Italian",
    "min_rating": 4.0,
    "extra_preferences": "family-friendly",
})

engine = FilterEngine(repo)
result = engine.filter(prefs)

if result.is_empty:
    print(result.message)
else:
    for r in result.candidates:
        print(r.name, r.rating)
```

## Phase 3: LLM Integration

Builds prompts from filtered candidates, calls **Groq** (OpenAI-compatible API), and parses structured JSON recommendations.

### Configuration

Copy `.env.example` to `.env` or export variables:

```bash
set GROQ_API_KEY=your-groq-key-here       # Windows
export GROQ_API_KEY=your-groq-key-here    # macOS/Linux

# Optional overrides
set LLM_MODEL=llama-3.3-70b-versatile
# set LLM_MODEL=llama-3.1-8b-instant      # faster / smaller
# set LLM_BASE_URL=https://api.groq.com/openai/v1
```

Get an API key at [console.groq.com/keys](https://console.groq.com/keys).

### Verify LLM integration

Dry run (prints prompt, no API call):

```bash
python scripts/test_llm.py --location Bangalore --budget medium --cuisine Italian --dry-run
```

Live LLM call:

```bash
python scripts/test_llm.py --location Bangalore --budget medium --cuisine Italian --min-rating 4.0
```

### Run tests

```bash
pytest tests/test_llm.py -m "not integration" -v
pytest tests/test_llm.py -v   # includes live LLM test when GROQ_API_KEY is set
```

### Project structure

```
src/llm/
├── config.py           # LLMConfig (Groq defaults)
├── prompt_templates.py # System + user prompt templates
├── prompt_builder.py   # build_prompt(), serialize_candidates()
├── client.py           # LLMClient (Groq via OpenAI SDK) + MockLLMClient
├── response_parser.py  # parse_llm_response(), fence stripping
├── schemas.py          # LLMResponse, PromptPayload
└── exceptions.py       # LLMError hierarchy
```

### Usage

```python
from src.data.repository import RestaurantRepository
from src.input import FilterEngine, validate_preferences
from src.llm import LLMClient

repo = RestaurantRepository()
repo.load()

prefs = validate_preferences({"location": "Bangalore", "budget": "medium"})
filtered = FilterEngine(repo).filter(prefs)

client = LLMClient.from_env()  # uses GROQ_API_KEY + Groq base URL
response = client.recommend(prefs, filtered.candidates, top_n=5)

for rec in response.recommendations:
    print(rec.rank, rec.name, rec.explanation)
print(response.summary)
```

### Expected LLM JSON response

```json
{
  "recommendations": [
    {"name": "Onesta", "rank": 1, "explanation": "Highly rated Italian option..."}
  ],
  "summary": "Top picks for medium-budget Italian dining in Bangalore."
}
```

## Phase 4: Recommendation Engine

Orchestrates filter → LLM → validate → enrich. Drops hallucinated restaurants, backfills gaps, and falls back to top-rated matches when the LLM fails.

### Verify recommendations

```bash
# Rule-based fallback only (no API key needed)
python scripts/recommend.py --location Bangalore --budget medium --no-llm

# Full pipeline with LLM
python scripts/recommend.py --location Bangalore --budget medium --cuisine Italian --min-rating 4.0
```

### Run tests

```bash
pytest tests/test_recommender.py -v
```

### Project structure

```
src/engine/
├── config.py        # top_n, fuzzy threshold
├── schemas.py       # Recommendation, RecommendationResult
├── parser.py        # parse_llm_json()
├── ranker.py        # merge, match, enrich, fallback
└── recommender.py   # Recommender.recommend()
```

### Usage

```python
from src.data.repository import RestaurantRepository
from src.engine import Recommender
from src.llm import LLMClient

repo = RestaurantRepository()
repo.load()

recommender = Recommender(repo, LLMClient.from_env(), top_n=5)
result = recommender.recommend({
    "location": "Bangalore",
    "budget": "medium",
    "cuisine": "Italian",
    "min_rating": 4.0,
})

for rec in result.recommendations:
    print(f"#{rec.rank} {rec.name} · ★{rec.rating} · ₹{rec.estimated_cost}")
    print(f"   {rec.explanation}")
```

## Phase 5: Output & UI

User-facing interfaces: Streamlit web app, CLI, and optional FastAPI REST API.

### Web UI (React — Dine.AI)

```bash
# Terminal 1 — API
cd c:\Users\ACER\MileStone1
$env:PYTHONPATH="c:\Users\ACER\MileStone1"
$env:APP_MAX_ROWS="20000"
& "C:\Users\ACER\anaconda3\python.exe" -m uvicorn src.app.api.routes:app --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend
cd c:\Users\ACER\MileStone1\frontend
npm install
npm run dev
```

Open **http://localhost:5173**

Pages:
- `/` — homepage with AI preference form (Dine.AI UI)
- `/recommend` — AI recommendation results + explanations
- `/restaurant/:id` — restaurant detail (why it was recommended)

Legacy Streamlit UI remains at `src/app/web.py` if needed.

### CLI

```bash
python -m src.app.main --location Bangalore --budget medium --cuisine Italian --no-llm
```

Without required flags, the CLI prints usage and exits with code 2.

### REST API

```bash
uvicorn src.app.api.routes:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/recommend ^
  -H "Content-Type: application/json" ^
  -d "{\"location\":\"Bangalore\",\"budget\":\"medium\",\"cuisine\":\"Italian\"}"
```

### Run tests

```bash
pytest tests/test_app.py -v
```

### Project structure

```
src/app/
├── main.py          # CLI entry point
├── web.py           # Streamlit UI
├── service.py       # Shared AppService
├── ui/
│   ├── forms.py     # Preference validation helpers
│   └── results.py   # Card formatting / display helpers
└── api/
    └── routes.py    # FastAPI /recommend + /health
```

## Documentation

- [Problem Statement](docs/problemStatement.md)
- [Architecture](docs/architecture.md)
- [Edge Cases](docs/edgeCases.md)

## Requirements

- Python 3.10+
- Network access for first-time dataset download (~574 MB cached locally by Hugging Face)
