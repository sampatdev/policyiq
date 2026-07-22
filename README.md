# PolicyIQ

An agentic RAG system for insurance policy documents. Upload a policy PDF, ask it questions, and get grounded, source-cited answers — or let it reason through multi-step tasks like comparing coverage or calculating premiums using tool-calling.

**Live demo:** https://policyiq-2.onrender.com
*(Free-tier hosting — the first request after inactivity may take 30-60 seconds to wake up.)*

---

## What this actually is

This project demonstrates three things, built as three layers on top of each other:

1. **RAG (Retrieval-Augmented Generation)** — documents are chunked, embedded, and stored as vectors. Questions are answered by retrieving the most relevant chunks and grounding an LLM's answer in them, rather than letting it guess.
2. **Agentic tool-use** — an LLM-driven loop where Claude decides which tools to call (document search, premium calculation, claim lookup, coverage comparison) and in what order, rather than following a fixed code path.
3. **Eval harness** — a golden dataset and automated scoring script that measures retrieval accuracy, answer correctness (via LLM-as-judge), latency, and helps catch regressions.

RAG and the agent are not two separate systems — the agent's `search_policy_documents` tool literally calls the same retrieval code the plain `/query` endpoint uses. The agent is RAG plus a reasoning layer on top.

---

## Architecture

```
PDF upload → text extraction (pypdf) → chunking → embeddings (Voyage AI)
    → stored in Postgres/pgvector (Supabase)

Question → embed question → pgvector similarity search → top-k chunks
    → Claude (grounded answer, cites source chunks)

Question → Claude decides which tool(s) to call → tool executes
    → result fed back to Claude → repeat until final answer
```

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| Database | PostgreSQL + pgvector (hosted on Supabase) |
| Embeddings | Voyage AI (`voyage-2`, 1024 dimensions) |
| LLM | Anthropic Claude (`claude-sonnet-4-5` for answers, `claude-haiku-4-5` for eval judging) |
| Hosting | Render (free tier) |
| ORM | SQLAlchemy |

---

## Endpoints

| Endpoint | Method | What it does |
|---|---|---|
| `/health` | GET | Basic liveness check |
| `/ingest` | POST | Upload a PDF, chunk + embed + store it |
| `/query` | POST | Plain RAG — ask a question, get a grounded answer from retrieved chunks |
| `/agent-query` | POST | Agentic — Claude decides which tool(s) to use (search, calculate premium, check claim, compare coverage) |

Interactive API docs (Swagger UI) are available at `/docs` on any running instance, e.g. `https://policyiq-2.onrender.com/docs`.

---

## Running this locally

### Prerequisites
- Python 3.12.4 (see note below on why this exact version)
- Docker Desktop (Mac/Windows) or Docker + Colima (Mac alternative)
- A Voyage AI API key — free tier at [dashboard.voyageai.com](https://dashboard.voyageai.com)
- An Anthropic API key — [console.anthropic.com](https://console.anthropic.com) (requires billing set up; pay-as-you-go)

### Setup (Mac / Linux)

```bash
git clone https://github.com/sampatdev/policyiq.git
cd policyiq

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Now open .env and fill in your real ANTHROPIC_API_KEY and VOYAGE_API_KEY

docker compose up -d
docker compose exec db psql -U policyiq -d policyiq -c "CREATE EXTENSION IF NOT EXISTS vector;"

uvicorn app.main:app --reload
```

### Setup (Windows)

```powershell
git clone https://github.com/sampatdev/policyiq.git
cd policyiq

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
:: Now open .env and fill in your real ANTHROPIC_API_KEY and VOYAGE_API_KEY

docker compose up -d
docker compose exec db psql -U policyiq -d policyiq -c "CREATE EXTENSION IF NOT EXISTS vector;"

uvicorn app.main:app --reload
```

Once running, visit `http://localhost:8000/docs` to try it interactively, or:

```bash
curl -X POST http://localhost:8000/ingest -F "file=@your_policy.pdf"
curl -X POST "http://localhost:8000/query?question=What is the waiting period for pre-existing conditions?"
```

### ⚠️ If port 5432 connection fails ("password authentication failed" or "connection refused")

This almost always means **something else on your machine is already using port 5432** — commonly a previously installed native Postgres (EnterpriseDB installer, Postgres.app, or Homebrew) that starts automatically in the background.

**Check what's listening:**
```bash
# Mac/Linux
sudo lsof -iTCP -sTCP:LISTEN -n -P | grep 5432

# Windows (PowerShell, as Administrator)
netstat -ano | findstr :5432
```

If something other than Docker shows up, stop it:
- **Mac, EnterpriseDB installer:** `sudo launchctl unload /Library/LaunchDaemons/postgresql-<version>.plist`
- **Mac, Homebrew:** `brew services stop postgresql@<version>`
- **Windows:** find the service in `services.msc` (search for "postgresql"), right-click → Stop, and set Startup type to Manual/Disabled if you don't need it running generally

Then fully reset the Docker volume and retry:
```bash
docker compose down -v
docker compose up -d
```

If you're on Mac using **Colima** instead of Docker Desktop, and the port still isn't reachable after freeing it, restart Colima to force it to re-establish port forwarding:
```bash
colima restart
docker compose up -d
```

### Running the eval suite

```bash
python -m eval.run_eval
```

This requires at least one document already ingested (see above) and real `expected_answer` values in `eval/golden_dataset.json` matching whatever you've actually ingested — the shipped dataset uses placeholder values that must be replaced with facts from your specific document before the scores are meaningful.

---

## Environment variables

| Variable | Where it's used | Notes |
|---|---|---|
| `DATABASE_URL` | Local: Docker Postgres. Production: Supabase pooler connection string. | If any character in your password isn't alphanumeric, URL-encode it (`@`→`%40`, `+`→`%2B`, `!`→`%21`, etc.) |
| `ANTHROPIC_API_KEY` | Claude API calls (answers + eval judging) | From console.anthropic.com |
| `VOYAGE_API_KEY` | Embedding generation | From dashboard.voyageai.com |
| `ENVIRONMENT` | Currently informational only | `development` locally, `production` on Render |

**Never commit `.env`.** It's already gitignored. Use `.env.example` as the template for what keys are needed.

---

## Known limitations / honest notes

- **Voyage AI free tier** (no payment method) caps requests at 3/minute and ~10K tokens/call. Ingestion batches embedding calls (3 chunks per call, ~21s apart) to stay under this — a real document can take 2-3 minutes to fully ingest as a result. Adding a payment method removes this ceiling without necessarily costing anything, since the free token allowance still applies.
- **`check_claim_status`** uses a mocked in-memory dataset, not a real claims database — this exists to demonstrate the tool-calling pattern, not as a production claims integration.
- **Render's free tier** spins down after ~15 minutes of inactivity; first request after idle has a cold-start delay.
- **Supabase's free tier** pauses the database after a week of no activity — resume manually from the Supabase dashboard if needed.
- Table creation uses SQLAlchemy's `create_all()`, which only creates missing tables and never alters existing ones — fine for this project's scale, but a real production system would use Alembic-managed migrations for schema changes instead.

See `DEPLOYMENT.md` for full infrastructure details, deployment steps, and every issue hit while standing this up.