# Autopsy.ai — Backend Engine & API Gateway

The backend service for **autopsy.ai** is built on FastAPI and implements the **Deep Policy Reasoning (DPR v2.0)** pipeline.

---

## 🏛️ Pipeline Stages

1. **`engine/retrieval_agent.py`**: Multi-source live search (Tavily, government archives, gazette releases).
2. **`engine/extractor_engine.py`**: Claim extraction with strict verbatim excerpt validation guardrails.
3. **`engine/drift_reasoning_engine.py`**: Pairwise temporal drift classifier (`consistent`, `explicit_update`, `silent_contradiction`, `insufficient_evidence`).
4. **`eval/eval_harness.py`**: Pre-deployment regression benchmark harness evaluated on 20+ ground-truth cases.

---

## 🚀 Quickstart

### 1. Setup Virtual Environment
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

### 4. Run Server
```bash
python run_server.py
```
The API is available at `http://127.0.0.1:8008` (Interactive Docs: `/docs`).

---

## 🧪 Running Benchmarks

```bash
python -m eval.eval_harness
```
