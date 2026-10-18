"""Where data lives and the few knobs you may want to tune."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MOCK = DATA / "mock"
CACHE = ROOT / ".cache"


def _first(paths):
    for p in paths:
        if p.exists():
            return p
    return None


def catalogue_path():
    """Returns (path, is_mock). The real organiser file wins; mock is only a fallback."""
    env = os.getenv("R3_CATALOGUE")
    if env:
        return Path(env), False
    names = ("catalogue.json", "catalogue.jsonl", "catalogue.csv",
             "catalog.json", "catalog.jsonl", "catalog.csv")
    p = _first([DATA / n for n in names])
    return (p, False) if p else (MOCK / "catalogue.json", True)


def policy_path():
    env = os.getenv("R3_POLICY")
    if env:
        return Path(env), False
    p = _first([DATA / n for n in ("policy.txt", "policy.md", "policies.txt")])
    return (p, False) if p else (MOCK / "policy.txt", True)


def questions_path():
    env = os.getenv("R3_QUESTIONS")
    if env:
        return Path(env)
    return _first([DATA / n for n in ("test_questions.json", "test_questions.jsonl",
                                      "test_questions.csv", "questions.json",
                                      "questions.jsonl", "questions.csv")])


# --- behaviour knobs -------------------------------------------------------
TOP_K = 3                 # products shown per answer
CLARIFY_THRESHOLD = 8     # more matches than this (and few filters) => ask a question
MIN_COS = float(os.getenv("R3_MIN_COS", "0"))       # raise after trying the real model
HIGH_COS = float(os.getenv("R3_HIGH_COS", "2.0"))   # >1 = "semantic rescue" disabled
