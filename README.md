# THRIVE Library Guide (chatbot prototype v1)

Search for the THRIVE Central Florida literature review in plain language. Ask for a topic ("resources on senior loneliness") and get the best-matching articles with a link and the sentence that matched. v1 is **retrieval only**: no API key, no cost, everything runs on your laptop. An optional LLM answer step is built but off.

Data: the public Google Sheet behind https://dssd-gnv.github.io/thrive-search/ (~456 rows, ~433 unique articles after merging duplicate titles).

## Run it

Needs Python 3.11.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt      # or requirements.lock for exact versions
.venv/bin/streamlit run src/thrive_chatbot/app.py         # opens the app
```

The first run downloads a small embedding model (~90 MB) and builds the index in `chroma_db/` (a few seconds). Later runs are instant.

Other commands (from the project root):

```bash
.venv/bin/python -m pytest -q                                          # tests
PYTHONPATH=src .venv/bin/python scripts/eval.py                        # score data/test_questions.csv
PYTHONPATH=src .venv/bin/python -m thrive_chatbot.cli "kindergarten readiness"   # quick terminal search
```

> macOS note: if Python 3.11 fails with `Symbol not found: _XML_SetAllocTrackerActivationThreshold` (pyexpat), prefix commands with `DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib`. This was needed on the machine this was built on.

## How it works

1. `data.py` downloads the sheet as CSV, finds the header row, maps columns by name (`config.COLUMN_MAP`), cleans it, and merges duplicate titles.
2. `index.py` turns each article (title + summary + problems + solutions + how to apply) into one embedding with `all-MiniLM-L6-v2` and stores it in a local Chroma database. Vectors are computed ahead of time; refreshing only re-embeds articles whose text changed.
3. `search.py` embeds the question, finds the closest articles (semantic) and the best word matches (BM25 keyword), merges both lists (reciprocal rank fusion), applies the optional THRIVE-area filter, and picks the reviewer sentence closest to the question as the "why it matched" text.
4. `app.py` is the Streamlit page: search, area filter, result cards, thumbs up/down (saved to `feedback.jsonl`, git-ignored), and a "Refresh data from sheet" button.
5. `answer.py` (off by default) asks a language model to write a 2-4 sentence answer from only the retrieved articles. Enable with `USE_LLM=true` and `LLM_MODEL=anthropic:<model>` or `openai:<model>` in `.env` (see `.env.example`) and install `langchain-anthropic` or `langchain-openai`.

## When the sheet changes

- New rows or edited text: click **Refresh data from sheet** (or `python -m thrive_chatbot.cli ... --refresh`). Only changed articles are re-embedded.
- Renamed or reordered columns, or the new lit-review layout: edit `COLUMN_MAP` in `src/thrive_chatbot/config.py`. Unknown extra columns are ignored. If a required column goes missing you get an error that lists the headers it saw.
- A two-row header (group band above column names) is detected automatically.

## What it does with messy data

| Situation | Behavior |
|---|---|
| Article has no link | Still searchable; shown as "link unavailable" |
| Empty fields, `-`, `N/A` | Treated as empty, left out of the card |
| Placeholder rows ("DO NOT DELETE") | Skipped |
| Same title twice | Merged: fuller row kept, categories combined |
| `Community&Social`, `Education (Case Studies...)` | Normalized to the five THRIVE areas; unknown labels (e.g. "Closed-Loop Referrals") pass through |
| Off-topic question | "I couldn't find that in the library." |
| Weakly related results | Shown with a "loosely related" warning |
| "hi", "what is thrive" | Short description of the library |
| Sheet unreachable | Falls back to `data/cache/thrive.csv` |

## Swapping the vector store (Pinecone)

Everything goes through LangChain's vector-store interface in `index.get_store()`. Replace the `Chroma(...)` call with `PineconeVectorStore(...)` (needs an account and key). Chroma-specific code lives only in `get_store()` and the `.get(...)`/`.delete(...)` calls in `refresh_index`.

## Known limits

- Answers come from reviewer summaries, not the full PDFs.
- The 18 test questions in `data/test_questions.csv` were written by the builder from the same sheet, so the score is optimistic. Add questions from real users (the "Use Cases" tab) before trusting it.
- Location words pull results toward Orlando-related articles ("pizza in Orlando" gets a loosely-related warning rather than a refusal).
- Search is English only.
