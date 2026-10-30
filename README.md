# ReliefRadar — AI Crisis-Gap Detector

> **Swim with TinyFish Hackathon Project**  
> **Team:** Next Gen Coders  
> **Problem Statement Category:** Software (Agentic AI / Open Innovation)  
> **Core Web Intelligence:** TinyFish Search API & TinyFish Fetch SDK  

ReliefRadar is an AI-powered disaster relief intelligence dashboard that autonomously finds where relief claims and ground reality do not match.

During sudden-onset disasters—such as the recent **cyclone and flooding across South Odisha (Ganjam & Gajapati)**—official announcements frequently claim restored services while isolated tribal hamlets and inundated urban wards remain cut off without clean drinking water, emergency medical power, or shelter kits. ReliefRadar eliminates blind spots by cross-verifying public reports, rejecting fabricated hallucinations, and categorizing actionable findings into a deterministic 4-state intelligence radar: **GAP**, **CONFLICT**, **UNKNOWN**, and **COVERED**.

---

## 1. Quick Start Guide (Windows / VS Code)

### Step 1: Install Dependencies
Ensure you are in the project root directory in PowerShell or Command Prompt:

```bash
pip install -r requirements.txt
```

### Step 2: Run the Prototype (Instant Demo Mode)
ReliefRadar features a **fully functional DEMO MODE** that runs **100% locally with zero API credentials required**:

```bash
python run.py
```

* **Interactive Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Interactive OpenAPI/Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Once opened in your browser, click **"Load Odisha Dataset"** to populate the verified South Odisha cyclone flood intelligence scenario.

---

## 2. API Key Security & Live Mode Configuration

ReliefRadar adheres strictly to API security best practices:
* **No hardcoded keys** exist anywhere in source code or documentation.
* `.gitignore` automatically prevents `.env` and SQLite database files from being committed.

### Where API Keys Are Read
API keys are loaded in [`backend/config.py`](backend/config.py) via `python-dotenv`:
```python
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "").strip()
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "").strip()
```

### How to Create `.env` in VS Code
1. Open the project root folder (`tinyfish/`) in VS Code.
2. In the Explorer sidebar, right-click and select **New File**, or copy `.env.example`:
   ```bash
   copy .env.example .env
   ```
3. Open your newly created `.env` file and paste your secret keys:
   ```dotenv
   TINYFISH_API_KEY=your_actual_tinyfish_api_key_here
   GROQ_API_KEY=your_actual_groq_api_key_here
   ```
4. Save the file (`Ctrl+S`).
5. Restart `python run.py`. The top navigation pill will immediately illuminate with **"Live APIs Connected"**.

> **Note:** In LIVE MODE, if keys are missing or invalid, the scan endpoint displays a clear configuration directive and will **never** silently substitute synthetic data for failed live API calls.

---

## 3. The 4-State Humanitarian Classification Engine

ReliefRadar enforces strict deterministic logic to ensure humanitarian accountability. The LLM is never permitted to assign final status codes:

| Classification | Color Code | Strict Deterministic Rule | South Odisha Demonstration Case |
| :--- | :--- | :--- | :--- |
| **GAP** | 🔴 Crimson (`#EF4444`) | Reported need with evidence explicitly proving zero supply or unmet shortfall. *(Missing info is never classified as GAP)*. | **Mohana, Gajapati**: 500 families cut off; 0 water tankers reached after culvert washout. |
| **CONFLICT** | 🔵 Royal Blue (`#3B82F6`) | Two comparable claims directly contradict one another for the same location and relief item. | **Berhampur, Ganjam**: District bulletin claims hospital generator 100% restored vs Red Cross reports ICU generator failed & neonatal ward in severe crisis. |
| **UNKNOWN** | 🟡 Amber (`#F59E0B`) | Need is reported, but supply fulfillment is unpublished. Refuses to invent or guess quantities. | **Chhatrapur, Ganjam**: 4,000 food rations requested; relief dispatch quantity is "Not published". |
| **COVERED** | 🟢 Emerald (`#22C55E`) | Verified evidence confirms that delivered supplies meet or exceed the requested need. | **Gopalpur, Ganjam**: 1,500 tarpaulins requested; 1,600 delivered by NDRF to Cyclone Shelter #4. |

### Anti-Hallucination: Verbatim Substring Quote Verifier
Every extracted fact in [`backend/quote_verifier.py`](backend/quote_verifier.py) is verified against the raw fetched document text using safe whitespace normalization. Any fabricated or unsupported quote is rejected before it can contribute to actionable findings.

---

## 4. Autonomous Data Pipeline

```text
       [ TinyFish Search API ]
                 ↓  (Queries district-specific crisis dispatches)
       [ TinyFish Fetch SDK ]
                 ↓  (Retrieves clean agent-ready Markdown text)
    [ Content Validation & Deduplication ]
                 ↓  (Rejects bot blocks and empty pages)
      [ Groq Structured Extraction ]
                 ↓  (Extracts needs & supplies into structured JSON)
     [ Verbatim Substring Quote Verifier ]
                 ↓  (Blocks hallucinations & unsupported quotes)
        [ Deterministic Gap Engine ]
                 ↓  (Classifies GAP, CONFLICT, UNKNOWN, COVERED)
   [ SQLite Storage & Audit Trails ]
                 ↓  (Stores facts, sources, and coordinator actions)
    [ Interactive Coordinator Dashboard ]
                 ↓  (Radar visualizer, side-by-side conflict comparison)
      [ Human-in-the-Loop Review ]
                    (Approve, Investigate, Reject dispatch orders)
```

---

## 5. Automated Verification & Testing

Run the full automated test suite containing 22 unit and integration tests:

```bash
pytest -v
```

### Verified Test Cases:
* **Quote Verifier**: Exact substring match, unicode curly quotes normalization, whitespace collapse, empty quote rejection, and fabricated quote defense.
* **Gap Engine**: Zero-supply GAP detection, strict protection ensuring missing supply is labeled UNKNOWN (not GAP), side-by-side CONFLICT detection, COVERED verification, partial fulfillment calculation (e.g., 30% fulfilled), and exclusion of unverified facts.
* **FastAPI Backend**: Health checks, real database metric aggregation, multi-parameter filtering, human review logging, CSV export, JSON export, and key security enforcement.

---

## 6. Project Architecture

```text
ReliefRadar/
├── backend/
│   ├── main.py              # FastAPI endpoints & static file server
│   ├── config.py            # Environment configuration & API key loading
│   ├── database.py          # SQLite engine & session generator
│   ├── models.py            # SQLAlchemy models (Source, ExtractedFact, Finding, ReviewAction)
│   ├── tinyfish_client.py   # TinyFish Search API & TinyFish Fetch SDK client
│   ├── extractor.py         # Groq LLM structured JSON extractor
│   ├── quote_verifier.py    # Strict verbatim substring quote verification
│   ├── gap_engine.py        # Deterministic 4-state classification engine
│   ├── pipeline.py          # End-to-end pipeline orchestrator
│   └── mock_data.json       # South Odisha Cyclone rich demonstration dataset
├── frontend/
│   ├── index.html           # Dark navy coordinator dashboard
│   ├── style.css            # Humanitarian styling, status tokens & responsive layout
│   └── app.js               # Dashboard controller, Chart.js charts, filters & review modals
├── tests/
│   ├── test_gap_engine.py   # Gap, Conflict, Unknown, and Covered logic tests
│   ├── test_quote_verifier.py # Anti-hallucination quote verification tests
│   └── test_api.py          # Integration tests for FastAPI endpoints & exports
├── .env.example             # Clean environment configuration template
├── .gitignore               # Strict exclusion of .env, .venv, and DB files
├── requirements.txt         # Project dependencies
├── run.py                   # Single-command startup entrypoint
└── README.md                # Project documentation
```
