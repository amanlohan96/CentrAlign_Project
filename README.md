# Autonomous AI Task Worker (Prototype)

An autonomous AI agent prototype designed to receive natural language business tasks, decompose them into an execution plan, operate computers and business software (filesystems, simulated web browsers, REST APIs, enterprise ERPs), detect and recover from errors, enforce human-in-the-loop safety boundaries, and independently verify outcome completion.

---

## 1. Quick Start & Run Instructions

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Windows / macOS / Linux

### Environment Setup
Activate the pre-configured virtual environment or create one:
```powershell
# In PowerShell (Windows):
.\venv\Scripts\Activate.ps1

# Or on macOS / Linux:
# source venv/bin/activate
```

If initializing a fresh virtual environment:
```bash
python -m venv venv
# Activate the venv, then:
pip install -r requirements.txt
```

---

## 2. Running the Prototype

### Option A: Interactive Web Mission Control Dashboard (Recommended)
Launch the full-featured real-time web interface:
```bash
python run_web.py
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

**Web Dashboard Features:**
- **Natural Language Task Prompt**: Execute custom tasks or select one-click demo presets.
- **Interactive Execution DAG**: Watch steps transition from `PENDING` &rarr; `IN_PROGRESS` &rarr; `SUCCESS`.
- **Live Working Memory Inspector**: Inspect discovered entities, visited paths, and scratchpad notes.
- **Simulated Enterprise ERP View**: Live accounts payable ledger updating in real-time as invoices are entered.
- **Human-in-the-Loop (HITL) Modal**: When an invoice exceeds the configured approval limit (e.g. $5,000), a modal appears to approve/reject with reviewer notes.
- **Independent Verification Certificate**: Visual badge and checklist verifying ground-truth ledger data.

---

### Option B: Interactive Terminal CLI Runner
Launch the rich-terminal command-line interface:
```bash
python run_demo.py
```
Provides an interactive menu with 5 demonstration scenarios:
1. **Archetypal Scenario**: Ingests latest invoice from Company X into ERP.
2. **HITL Safety Guardrail**: High-value capital expense ($18,500 GPU cluster) triggering interactive approval prompt.
3. **Self-Healing & Format Recovery**: Automatic detection of non-ISO dates, self-healing normalization, and retry.
4. **Structured JSON Processing**: Ingestion of structured JSON invoices (Apex Logistics).
5. **Custom Goal**: Enter arbitrary free-form tasks.

---

### Option C: Automated Test Suite
Run the test suite:
```bash
pytest -v
```
All 9 end-to-end and unit tests pass with zero external cloud dependencies.

---

## 3. High-Level Architecture

The prototype is structured around a decoupled, closed-loop ReAct execution model:

```
[ Natural Language Goal ]
          │
          ▼
   Task Planner (DAG Decomposition)
          │
          ▼
   Safety Guardrails ──(Threshold Exceeded)──► Human Approval Modal
          │ (Approved)                                │ (Resumed)
          ▼                                           ▼
   ReAct Execution Loop ◄─────────────────────────────┘
   ├── Tool Execution (Files, Browser, ERP, API)
   ├── Observation & Working Memory Store
   └── Self-Healing Engine (Error Detection & Dynamic Replanning)
          │
          ▼
   Independent Outcome Verifier (Target System Ground-Truth Query)
          │
          ▼
   Completion Summary & Certified Evidence Dossier
```

For complete technical specifications, see [ARCHITECTURE.md](file:///c:/Users/raman/OneDrive/Desktop/New%20folder%20(2)/ARCHITECTURE.md).

---

## 4. Key Technical & Design Decisions

1. **Independent Verification Subsystem (`core/verifier.py`)**:
   - Rather than assuming success because a tool returned HTTP 200, the worker performs post-execution queries directly against the target ERP system. It checks record existence, exact numerical amounts, ISO date formats, and cryptographic SHA-256 state checksums.
2. **Self-Healing & Adaptive Replanning (`core/planner.py` & `core/agent.py`)**:
   - When tools encounter errors (e.g., ERP rejects invalid date format `12/04/2024` or an initial search yields zero files), the worker classifies the failure, synthesizes a dynamic remediation step (`date_normalizer` or archive search), updates working memory, and retries the operation.
3. **Deterministic Safety Guardrails (HITL) (`core/guardrails.py`)**:
   - Automated workers operating financial systems must adhere to policy thresholds. Invoices above a configurable limit (default: $5,000.00) pause the worker in `WAITING_FOR_APPROVAL` until an authorized human grants permission.
4. **Dual Cognitive Engine (Local + Cloud LLM) (`core/llm_engine.py`)**:
   - The system works out-of-the-box using an intelligent local cognitive engine, requiring no external API keys or network calls. If a `GEMINI_API_KEY` or `OPENAI_API_KEY` is supplied, it seamlessly switches to cloud LLM reasoning.
5. **Simulated Enterprise Environment (`simulated_enterprise/`)**:
   - Built a realistic company ecosystem containing a document storage vault (PDFs, JSON, TXT invoices), an accounting ERP ledger with business validations, and a simulated browser DOM for UI automation.

---

## 5. Walkthrough of the Archetypal Scenario

**User Goal:**
> *“Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done.”*

**Execution Steps:**
1. **Goal Decomposition**: Planner generates a 6-step DAG:
   - Search vault for "Company X" documents.
   - Read content from discovered candidate file (`acme_invoice_nov2024.pdf`).
   - Extract structured entities (Vendor: Acme Cloud Corp, Inv #: INV-2024-9102, Amount: $4,850.00, Due Date: 2024-12-04).
   - Evaluate safety policies (Amount < $5,000 threshold &rarr; safe to proceed).
   - Post invoice into Internal ERP ledger.
   - Independently query ERP ledger to verify record creation and value integrity.
   - Dispatch completion notification to user with proof of execution.
2. **Result Evidence**:
   - Record created: `ERP-INV-1002`
   - Verified Checksum: `af6fc1b4bd7822e2`
   - Data Fidelity: 100% match across 5 independent ledger checks.

---

## 6. Known Limitations

- **Headless Browser Execution**: The prototype uses a simulated DOM engine rather than a live Chromium instance (e.g. Playwright) to eliminate heavy browser binary dependencies and ensure instant execution on any machine.
- **OCR Depth**: PDF reading is powered by text stream extraction (`pypdf`). Low-resolution scanned images without text streams require integrating a full OCR engine like Tesseract or Google Cloud Vision.
- **Single-Agent Scope**: The prototype uses a centralized ReAct orchestrator rather than a multi-agent swarm (e.g. separate Planner, Critic, and Worker agents).

---

## 7. What to Build Next (Future Roadmap)

1. **Multi-Modal Visual Browser Automation**:
   - Integrate Playwright with vision-capable models (Gemini Flash Vision) for screenshot-based element grounding and resilient coordinate-based clicking.
2. **Transaction Rollback & Compensating Actions**:
   - If a multi-step task fails mid-execution (e.g. payment sent but ERP update failed), automatically trigger compensating actions to return external systems to a clean state.
3. **Human Clarification Dialogue**:
   - Enhance the clarification loop so the agent can ask multi-turn clarifying questions when task instructions are underspecified or ambiguous.
4. **Persistent Vector Knowledge Base**:
   - Store historical company policies, vendor catalogs, and past task trajectories in ChromaDB/pgvector to accelerate task execution and improve few-shot accuracy.

---

## 8. Assumptions Made

- **Company X Mapping**: In enterprise settings, "Company X" frequently corresponds to an approved vendor pseudonym; mapped here to "Acme Cloud Corp" (with November 2024 being the latest invoice over October 2024).
- **Security Boundaries**: Autonomous actions exceeding $5,000.00 USD represent material financial commitments and require human supervisor authorization per standard corporate internal controls.
- **ISO-8601 Compliance**: Internal ERP databases mandate `YYYY-MM-DD` date formatting; unstructured vendor inputs in alternative formats must be normalized before ledger commit.

---

## 9. Models, Frameworks, and Components Used

- **Runtime**: Python 3.13
- **Web & API Framework**: FastAPI + Uvicorn
- **Data Validation & Modeling**: Pydantic v2
- **Document Processing**: PyPDF v6 (PDF parsing & stream inspection)
- **Terminal UI**: Rich (colored tables, panels, and interactive prompts)
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS Grid (zero frontend build step required)
- **Testing**: Pytest
- **Cognitive Engines**: Local Autonomous Cognitive Engine (built-in) + optional Google Generative AI (`gemini-1.5-flash`) via `google-generativeai`.
