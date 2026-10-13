# SNAP — SAP Security Note AI Patch

**SNAP** (SAP Security Note AI Patch) is an AI-powered tool that automates SAP Patch Tuesday triage. It matches SAP security notes against your organization's SAP landscape using a two-pass analysis engine — deterministic rules plus Claude AI — and presents results in a web dashboard for human review and approval.

## What It Does

Every SAP Patch Tuesday, SAP releases security notes. SNAP automates the triage:

1. **Ingest** security notes (Excel upload, SAP portal fetch, or API)
2. **Match** against your SAP landscape using two passes:
   - **Pass 1 — Rules Engine**: Deterministic version/SP-level matching (high confidence)
   - **Pass 2 — AI Analyzer**: Claude analyzes notes the rules couldn't match (medium confidence)
3. **Review** results in a web dashboard — approve, dismiss, or defer each match
4. **Route** approved patches to your change management process

---

## Installation Guide

### Prerequisites

- **Python 3.11+** or **Docker**
- Access to an **OpenAI-compatible AI gateway** (LiteLLM, Azure OpenAI, Bedrock proxy, etc.) — if other AI agents already run in your environment, use the same endpoint
- **SAP S-user credentials** (only if using the "Fetch Latest" auto-download feature — not needed for manual Excel upload)

### Step 1: Get the Code

```bash
git clone <repository-url> snap
cd snap
```

### Step 2: Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and set the required values:

| Variable | Required? | Description |
|---|---|---|
| `AI_BASE_URL` | **Yes** (for analysis) | Your AI gateway URL, e.g. `https://your-gateway.com` |
| `AI_API_KEY` | **Yes** (for analysis) | API key for the AI gateway |
| `AI_MODEL` | No | Model identifier (default: `bedrock.anthropic.claude-sonnet-4-5`) |
| `SECRET_KEY` | **Yes** | Random string for session signing — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SAP_USERNAME` | Only for auto-fetch | SAP portal S-user login |
| `SAP_PASSWORD` | Only for auto-fetch | SAP portal S-user password |
| `HTTPS_PROXY` | If behind a proxy | Corporate proxy URL |

> **Note:** If your environment already has `AI_BASE_URL` and `AI_API_KEY` set at the system/container level for other agents, SNAP picks them up automatically — no duplicate config needed.

See [.env.example](.env.example) for the full list with descriptions.

### Step 3: Set Up Dashboard Users

Edit `config/users.yaml` to define who can log into the dashboard.

Generate a bcrypt password hash:
```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"
```

Paste the hash into `config/users.yaml`:
```yaml
users:
  - username: admin
    password_hash: "$2b$12$..."   # <-- paste hash here
    role: admin
    email: admin@yourcompany.com
```

> **WARNING:** If `password_hash` is left empty, the admin password defaults to `admin`. Always set a real password before deploying to any shared environment.

### Step 4: Start the Server

**With Docker (recommended for production):**
```bash
cd deploy
docker-compose up -d
```

**Without Docker (development):**
```bash
pip install -e ".[dev]"
uvicorn src.main:create_app --factory --host 0.0.0.0 --port 8000
```

### Step 5: First Use

1. Open **http://your-server:8000** and log in
2. **Upload your SAP landscape** — go to Landscape Manager, drag-and-drop your system inventory Excel/CSV
3. **Upload SAP security notes** — go to Security Notes, upload the SAP Patch Tuesday Excel export (or click "Fetch Latest" if SAP credentials are configured)
4. **Run Analysis** — the two-pass engine matches notes to your systems
5. **Review results** — approve, dismiss, or defer each match

---

## Configuration Files

All config lives in the `config/` directory:

| File | Purpose |
|---|---|
| `config/users.yaml` | Dashboard login users and roles |
| `config/rules.yaml` | Matching rules: version strategies, component aliases, tier weights |
| `config/component_map.yaml` | SAP component canonical names and aliases |

These are mounted as a Docker volume — edit them without rebuilding the container.

---

## Architecture

```
SAP Notes (Excel/API/MCP) ──→ Ingestion ──→ DB
                                              ↓
SAP Landscape (Excel/CSV) ──→ Loader ──→ Normalizer ──→ Component Index
                                                              ↓
                                              ┌───────────────┴───────────────┐
                                              ↓                               ↓
                                        Pass 1: Rules                   Pass 2: AI
                                        (deterministic)              (Claude, if needed)
                                              ↓                               ↓
                                              └───────────────┬───────────────┘
                                                              ↓
                                                        Consolidator
                                                     (dedupe + score)
                                                              ↓
                                                        Dashboard
                                                  (review / approve)
```

- **Pass 1 (Rules Engine)** runs first — fast, high-confidence, SP-level version matching
- **Pass 2 (AI Analyzer)** runs only when rules found no matches AND no SP data exists — avoids unnecessary AI calls
- Results are consolidated, scored by `CVSS × confidence × tier weight`, and sorted by priority

---

## Data Storage

- **Database:** SQLite at `data/snap.db` (auto-created on first run)
- **Persistent volumes:** Mount `data/` and `config/` when using Docker

---

## Development

```bash
pip install -e ".[dev]"
pytest -v
```
