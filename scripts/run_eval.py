"""Run the assistant over the organisers' test questions and write honest reports.

    python scripts/run_eval.py                       # uses data/test_questions.*
    python scripts/run_eval.py --questions path.json --limit 20

Outputs (reports/):  per_query_results.csv · summary.md · summary.json · predictions.jsonl
          + official_evaluate_output.txt when the organisers' evaluate.py was actually run.

Honesty rules: metrics that need hidden labels or the official judge are reported as "n/a"
unless they were really computed. Nothing is estimated or invented."""
import argparse
import csv
import json
import os
import shlex
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from r3 import config                      # noqa: E402
from r3.assistant import Session          # noqa: E402
from r3.factory import build_assistant    # noqa: E402

Q_KEYS = ("question", "query", "q", "text", "prompt", "user_query")
ID_KEYS = ("id", "qid", "question_id")
TURN_KEYS = ("turns", "conversation", "messages")
EXP_KEYS = ("expected_behavior", "expected_behaviour", "expected", "label", "behavior", "behaviour")


def load_questions(path):
    path = Path(path)
    if path.suffix == ".csv":
        rows = list(csv.DictReader(open(path, newline="", encoding="utf-8-sig")))
    elif path.suffix == ".jsonl":
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else next(v for v in data.values() if isinstance(v, list))
    out = []
    for i, r in enumerate(rows):
        if isinstance(r, str):
            r = {"question": r}
        low = {k.lower(): v for k, v in r.items()}
        turns = next((low[k] for k in TURN_KEYS if k in low), None)
        if isinstance(turns, list):
            turns = [t if isinstance(t, str) else t.get("content", "") for t in turns
                     if isinstance(t, str) or t.get("role", "user") == "user"]
        else:
            q = next((low[k] for k in Q_KEYS if k in low), None)
            if q is None:
                raise ValueError(f"Row {i}: no question field found among {Q_KEYS}. Keys: {list(r)}")
            turns = [q]
        out.append({"id": str(next((low[k] for k in ID_KEYS if k in low), i + 1)), "turns": turns,
                    "expected": next((low[k] for k in EXP_KEYS if k in low), None)})
    return out


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions"); ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args()
    qpath = Path(a.questions) if a.questions else config.questions_path()
    if not qpath or not qpath.exists():
        sys.exit("No test questions found. Put the organisers' file in data/test_questions.json (or .jsonl/.csv) "
                 "or pass --questions PATH. Nothing was evaluated.")
    questions = load_questions(qpath)[: a.limit]
    asst = build_assistant()
    out = Path(a.out); out.mkdir(exist_ok=True)

    rows, preds = [], []
    for q in questions:
        session, reply, total_ms = Session(), None, 0.0
        for turn in q["turns"]:                      # fresh conversation per question; multi-turn replayed in order
            reply = asst.chat(session, turn)
            total_ms += reply.latency_ms
        v = reply.validation
        rows.append({
            "id": q["id"], "question": " || ".join(q["turns"]), "outcome": reply.outcome, "behaviour": reply.behaviour,
            "answer": reply.text.replace("\n", " ⏎ "), "cited_ids": ";".join(reply.cited_ids),
            "cited_policy_sections": ";".join(reply.cited_sections), "validator_ok": v.ok,
            "validator_errors": "; ".join(v.errors), "hallucinated_prices": v.hallucinated_prices,
            "uncited_claims": v.uncited_claims, "facts_checked": v.claims_checked,
            "latency_ms": round(total_ms, 2), "llm_tokens_in": 0, "llm_tokens_out": 0, "cost_usd": 0.0,
            "expected": q["expected"] if q["expected"] is not None else "",
        })
        preds.append({"id": q["id"], "question": q["turns"][-1], "answer": reply.text, "behaviour": reply.behaviour,
                      "outcome": reply.outcome, "citations": {"products": reply.cited_ids, "policy": reply.cited_sections},
                      "latency_ms": round(total_ms, 2)})

    with open(out / "per_query_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (out / "predictions.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in preds), encoding="utf-8")

    n = len(rows)
    lat = [r["latency_ms"] for r in rows]
    cnt = lambda k: sum(r["behaviour"] == k for r in rows)
    labelled = [r for r in rows if r["expected"] in ("answer", "clarify", "refuse")]
    S = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "data": {"mock": asst.is_mock, "catalogue": asst.catalogue_file, "policy": asst.policy_file,
                 "products": len(asst.products), "embedder": asst.embedder_name, "questions_file": str(qpath)},
        "questions": n,
        "behaviour_counts": {k: cnt(k) for k in ("answer", "clarify", "refuse", "chat")},
        "validator_pass_rate": round(sum(r["validator_ok"] for r in rows) / n, 4),
        "answers_blocked_by_validator": sum(r["outcome"] == "blocked" for r in rows),
        "hallucinated_prices_in_shown_answers": sum(r["hallucinated_prices"] for r in rows if r["outcome"] != "blocked"),
        "hallucinated_prices_caught_before_display": sum(r["hallucinated_prices"] for r in rows),
        "uncited_factual_claims_caught": sum(r["uncited_claims"] for r in rows),
        "factual_claims_checked": sum(r["facts_checked"] for r in rows),
        "latency_ms": {"mean": round(statistics.mean(lat), 2), "p50": round(pct(lat, .5), 2),
                       "p95": round(pct(lat, .95), 2), "max": round(max(lat), 2)},
        "tokens_and_cost": "0 tokens / $0 — no LLM or paid API is called; answers are built by deterministic code",
        "refusal_accuracy": "n/a (needs hidden labels)", "helpfulness": "n/a (needs the official judge)",
        "groundedness_official": "n/a (official evaluate.py not run)",
    }
    if labelled:
        ok = sum(r["behaviour"] == r["expected"] for r in labelled)
        S["label_agreement"] = f"{ok}/{len(labelled)} = {ok / len(labelled):.1%} (labels from questions file)"

    # --- the organisers' evaluate.py: run only if we can do so without guessing its interface ---
    ev = Path(os.getenv("R3_EVALUATE_PATH", ROOT / "evaluate.py"))
    cmd = os.getenv("R3_EVALUATE_CMD")      # e.g.  python evaluate.py --predictions {predictions}
    if ev.exists() and cmd:
        full = shlex.split(cmd.format(predictions=out / "predictions.jsonl"))
        res = subprocess.run(full, capture_output=True, text=True, cwd=ROOT)
        (out / "official_evaluate_output.txt").write_text(f"$ {' '.join(full)}\n\n{res.stdout}\n{res.stderr}", encoding="utf-8")
        S["groundedness_official"] = f"evaluate.py exit code {res.returncode}; see reports/official_evaluate_output.txt"
    elif ev.exists():
        S["groundedness_official"] = ("evaluate.py found but NOT run: its command line is unknown here. Read `python evaluate.py --help`, "
                                      "then set R3_EVALUATE_CMD (see README) and re-run.")
    (out / "summary.json").write_text(json.dumps(S, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [f"# R3 evaluation summary", f"_Generated {S['generated']}_", ""]
    if asst.is_mock:
        md += ["> ⚠️ **MOCK DATA.** These numbers describe the sample dataset, not the organisers' catalogue.", ""]
    md += ["| Metric | Value |", "|---|---|"]
    flat = {"Questions run": n, "Answered / clarified / refused": f"{S['behaviour_counts']['answer']} / {S['behaviour_counts']['clarify']} / {S['behaviour_counts']['refuse']}",
            "Validator pass rate": f"{S['validator_pass_rate']:.1%}", "Answers blocked by validator": S["answers_blocked_by_validator"],
            "Hallucinated prices shown to user": S["hallucinated_prices_in_shown_answers"],
            "Hallucinated prices caught before display": S["hallucinated_prices_caught_before_display"],
            "Factual claims re-checked against sources": S["factual_claims_checked"],
            "Latency mean / p50 / p95 / max (ms)": " / ".join(str(S["latency_ms"][k]) for k in ("mean", "p50", "p95", "max")),
            "Tokens & cost": S["tokens_and_cost"], "Refusal accuracy": S["refusal_accuracy"],
            "Helpfulness": S["helpfulness"], "Official groundedness score": S["groundedness_official"]}
    if "label_agreement" in S: flat["Behaviour agreement with provided labels"] = S["label_agreement"]
    md += [f"| {k} | {v} |" for k, v in flat.items()]
    md += ["", f"Data: `{asst.catalogue_file}` ({len(asst.products):,} products), embedder `{asst.embedder_name}`."]
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
