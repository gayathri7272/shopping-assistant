"""Policy assistant: answers ONLY by quoting sentences from the policy document, with the section cited.
No generation, so nothing can be invented. If the policy doesn't cover the question, it refuses."""
import re

import numpy as np

from .nlp import POLICY_STEMS
from .text import STOP, stem, tokens

GENERIC = {"order", "orders", "buy", "bought", "purchase", "purchased", "many", "much", "long", "take", "takes",
           "get", "got", "can", "will", "pay", "paid", "customer", "store", "shop", "website", "online"}


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


class PolicyAssistant:
    def __init__(self, sections, embedder):
        self.sections = sections
        self.by_label = {s.label: s for s in sections}
        self.stems = [{stem(t) for t in tokens(s.label + " " + s.text)} for s in sections]
        self.all_stems = set().union(*self.stems) if self.stems else set()
        self.emb = embedder.encode([s.label + ". " + s.text for s in sections])
        self.embedder = embedder

    def answer(self, query, kinds=(), product_words=()):
        """Returns (status, text, cited_labels). status: 'answer' | 'refuse'."""
        q = [t for t in tokens(query) if t not in STOP]
        qs = {stem(t) for t in q}
        pw = {stem(w) for w in product_words}
        specific = [t for t in q if stem(t) not in POLICY_STEMS and t not in GENERIC and not t.isdigit()]
        missing = [t for t in specific if stem(t) not in self.all_stems]
        prod_missing = [t for t in missing if stem(t) in pw]      # "warranty on headphones": a product type, not a policy topic
        specific = [t for t in specific if t not in prod_missing]
        missing = [t for t in missing if t not in prod_missing]

        if specific and len(missing) == len(specific):
            return "refuse", self._refuse(missing), []

        # pick the best section: title match counts triple, then body overlap, then embeddings
        qv = self.embedder.encode([query])[0]
        cos = self.emb @ qv
        scores = []
        for i, s in enumerate(self.sections):
            title = {stem(t) for t in tokens(s.label)}
            scores.append(3 * len(qs & title) + len(qs & self.stems[i]) + 0.5 * float(cos[i]))
        best = int(np.argmax(scores))
        if len(qs & self.stems[best]) == 0:
            return "refuse", self._refuse(specific or q[:3]), []
        sec = self.sections[best]

        sents = sentences(sec.text)
        if specific:
            ranked = sorted(range(len(sents)), key=lambda i: -len(qs & {stem(t) for t in tokens(sents[i])}))
            chosen = sorted(i for i in ranked[:2] if qs & {stem(t) for t in tokens(sents[i])})
            if not chosen:
                return "refuse", self._refuse(specific), []
        else:
            chosen = list(range(min(4, len(sents))))
        lines = [f"> “{sents[i]}” [Policy: {sec.label}]" for i in chosen]
        text = f"Here is what the policy says ({sec.label}):\n" + "\n".join(lines)
        gone = missing + prod_missing
        if gone:
            text += (f"\n\nThe policy does not mention {', '.join(gone)} specifically, "
                     "so I can't say how it applies beyond the text above.")
        return "answer", text, [sec.label]

    def _refuse(self, missing):
        what = ", ".join(missing) if missing else "that"
        return (f"I can't answer that from the supplied policy document: it does not mention {what}. "
                "I only answer questions about returns, shipping and warranty using that text, and I won't guess.")
