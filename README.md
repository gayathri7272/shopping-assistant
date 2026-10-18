# R3 — The Shopping Assistant That Doesn't Lie

Offline, no API keys. Every price, stock status, rating and policy sentence on screen is **copied from the
catalogue/policy by Python code** and then **re-verified by a validator** before it is shown.

> **Status:** built and tested on a **MOCK dataset** (200 generic products). The organisers' catalogue, policy,
> questions, models and `evaluate.py` were not available when this was written — see *Limitations* and *Switch to the real data*.

## Run it (Windows / macOS / Linux, Python 3.10+)
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate        macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/make_mock_data.py        # only needed if data/mock/ is missing
python -m unittest -v                   # 18 tests, ~1 second
streamlit run app.py                    # opens http://localhost:8501
python scripts/run_eval.py              # needs data/test_questions.* (see below)
```

## Switch to the real data (10 minutes)
1. Copy the organisers' files to `data/catalogue.json|jsonl|csv`, `data/policy.txt`, `data/test_questions.*`.
2. Open `r3/data_loader.py` → `ALIASES`. If their column names differ (e.g. `product_name`), add them there. Nothing else changes.
3. Embedding model: find where it is cached, then `export R3_EMBED_MODEL=/path/to/model` (Windows: `set R3_EMBED_MODEL=...`) and `pip install sentence-transformers`.
   The sidebar shows which embedder is active. If it still says `fallback-hashing-ngram`, the model did not load.
4. Run `python -m unittest -v`. Tests marked *mock only* are skipped on real data; the rest check behaviour against the real catalogue.
5. Delete `.cache/` after swapping data (embeddings are cached per file).
6. Official scorer: run `python evaluate.py --help`, then e.g.
   `export R3_EVALUATE_CMD="python evaluate.py --predictions {predictions}"` and `python scripts/run_eval.py`.
   The runner writes `reports/predictions.jsonl` and saves the scorer's real output; it never invents a score.

## How it works (explain this in 60 seconds)
```
message → nlp.py (price/rating/stock/category/attribute filters, typo repair, Hindi/Telugu filler words)
        → assistant.py routes:  product search | product ID/“the 2nd one” facts | policy | clarify | refuse
        → retriever.py: EXACT filters first, then embedding ranking, then a word-coverage guard
        → answer text is built only from catalogue fields  (assistant.py: fmt_price/fmt_stock/…)
        → validator.py re-checks every ₹, stock word, ★, [ID …], [Policy: …] and quote → blocks on any mismatch
```
* **A product is shown only if it contains every word you typed** (or a synonym; numbers like “17” must match exactly) — so “iPhone 17 Pro Max” never returns an iPhone 15.
* **Policy answers are quotes**, not generated text. No policy text for the question ⇒ refusal.
* **Missing info stays missing**: no price → “price not listed”.
* **Multi-turn**: filters accumulate; a new budget replaces the old one; a new product type replaces the old topic; “forget the budget” / “start over” remove things. The sidebar always shows what is remembered — nothing is silently assumed.
* **Ambiguity**: >8 matches and fewer than 2 filters ⇒ it asks a question using real options from the matches (“just show me the top ones” skips it).

Files: `r3/` (config, text, data_loader, embedder, nlp, retriever, policy, validator, assistant, factory) · `app.py` · `scripts/` · `tests/`.

## Demo script (≈3 min)
1. “I want cotton clothes” → it asks a clarifying question with real options. 2. “Under ₹2,000” → cards with IDs, ₹, stock, ★, citations.
3. “is the first one in stock?” → fact lines, each cited. 4. “forget the budget” → sidebar updates. 5. “iPhone 17 Pro Max” → clear “not in catalogue”.
6. “price of <a fake ID>” → not found. 7. “how many days to return an item?” → quoted policy + section. 8. “do you offer gift wrapping?” → refusal.
9. “cotten shrt under 1500” / “sasta joota 2000 ke andar” → typos & code-mixed handled. 10. Open `reports/summary.md` and the CSV.

## Limitations (honest list)
* **Not yet run on the real organiser files**; every number in `reports/` from the mock data is labelled MOCK. Real-catalogue behaviour (attribute names, category tree, relevance thresholds) needs tuning — expect an hour of iteration.
* **`evaluate.py` is not integrated yet**: its command line is unknown to us. The runner is ready to call it (see step 6) but has not.
* The **instruction-following model is not used**. Answers are template-built (zero hallucination risk, but less conversational). If you add it, only let it rephrase text that still passes `validator.validate`.
* The Streamlit UI was syntax-checked but **not launched** in the environment where this was written (no network to install Streamlit). Run it first and tell us any error.
* Refusal accuracy, helpfulness and groundedness scores need the hidden labels / official judge: reported `n/a` until then.
* Rule-based language handling covers common Hindi/Telugu filler words only; extend `STOP` and `SYN_RAW` in `r3/text.py`.
* FAISS is not used on purpose: 5,000 vectors are searched with one NumPy matrix product (~20 ms).
