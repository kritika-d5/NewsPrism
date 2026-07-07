# NewsPrism — The Agentic Bias Ledger

NewsPrism analyzes how different outlets frame the **same** event. A newsroom of
autonomous agents ingests articles, groups coverage of the same story, verifies the
facts each source reports, flags what they omit, and computes a transparent, dynamically
weighted **Bias Index**.

## What makes it agentic

The pipeline is a real multi-agent loop, not a fixed script. Each stage streams its
progress live to the UI (Server-Sent Events), so you can watch the newsroom work:

| Agent | Role |
|-------|------|
| **Editor-in-Chief** (orchestrator) | Plans coverage, classifies the story, decides whether to loop for more sources |
| **Ingestor / Scraper** | Searches the news wire and scrapes full article text |
| **Researcher** | When coverage is thin or one-sided, re-queries for more diverse sources |
| **Story Clusterer** | Embeds articles and runs **DBSCAN** to group coverage of the same event |
| **Fact-Checker** | Extracts candidate claims and cross-checks them across sources (supported / contradicted / unverified) |
| **Bias Auditor** | Infers **dynamic weights** for the Bias Index based on the story, then self-corrects them from evidence |
| **Copy Editor** | Consolidates and persists the finished report |

The Editor-in-Chief and Fact-Checker use the **Groq API** (Llama 3.3 70B) to make
routing decisions (e.g. *ingest more vs. proceed*) and to infer the Bias Index weights,
so the same query can take a different path depending on what the evidence looks like.

## The Bias Index

A 0–100 score for how strongly a source *frames* a story (not whether it is "right"):

```
index = 100 × ( w_tone·Δtone + w_lex·lexical + w_om·omission + w_cons·consistency + dissonance ) ÷ 1.3
```

- **Δtone** — deviation of this source's sentiment from the cluster average (RoBERTa sentiment)
- **lexical** — density of loaded / emotive / prescriptive language (spaCy)
- **omission** — share of the cluster's verified facts the source leaves out (semantic omission detection)
- **consistency** — internal subjectivity vs. the shared facts
- **dissonance** — penalty when tone clashes with the emotional weight of the verified facts

Weights (`w_*`) are set per-story by the Bias Auditor agent and shown in the UI, so the
score is fully transparent — the cluster page breaks down every source's contribution.

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python run.py            # http://localhost:8000  (docs at /docs)
```

### Frontend

```bash
cd frontend
npm install
npm run dev              # http://localhost:3000
```

## Environment Variables

Create `.env` in `backend/`:

- `MONGODB_URL` — MongoDB connection string (stores articles & clusters)
- `GROQ_API_KEY` — Groq API key (agent reasoning + fact verification)
- `NEWSAPI_KEY` — NewsAPI key (article discovery)
- `PINECONE_API_KEY` — *optional*; clustering runs locally with DBSCAN and does not require it

## Tech Stack

- **Backend**: FastAPI, MongoDB (Motor), Groq (Llama 3.3 70B), SSE streaming
- **Frontend**: React, Vite, Tailwind CSS, Chart.js
- **NLP / ML**: SentenceTransformers (all-MiniLM-L6-v2), scikit-learn (DBSCAN), spaCy, Hugging Face Transformers
