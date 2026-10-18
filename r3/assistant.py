"""The brain: routes each message (product search / product fact / policy / clarify / refuse),
keeps the user's constraints between turns, and validates every answer before returning it."""
import time
from dataclasses import dataclass, field

from . import config
from .nlp import Parsed, Vocab, parse
from .policy import PolicyAssistant
from .retriever import Retriever
from .text import stem
from .validator import Validation, validate


# ---------- formatting (the ONLY place prices/stock/ratings become text) ----------
def fmt_price(x):
    if x is None:
        return "price not listed"
    return f"₹{x:,.0f}" if float(x).is_integer() else f"₹{x:,.2f}"


def fmt_stock(s):
    return {True: "In stock", False: "Out of stock"}.get(s, "stock status not listed")


def fmt_rating(r):
    return "no rating listed" if r is None else f"★{r:.1f}"


def cite(p):
    return f"[ID {p.id}]"


@dataclass
class Session:
    topic: list = field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    min_rating: float | None = None
    stock: bool | None = None
    categories: list = field(default_factory=list)
    attrs: list = field(default_factory=list)
    sort: str | None = None
    last: list = field(default_factory=list)      # product IDs shown in the previous answer
    history: list = field(default_factory=list)   # [(role, text)]

    def clear(self):
        self.__init__(history=self.history)

    @property
    def empty(self):
        return not (self.topic or self.attrs or self.categories or self.price_min is not None
                    or self.price_max is not None or self.min_rating is not None or self.stock is not None)

    @property
    def amounts(self):
        return {x for x in (self.price_min, self.price_max) if x is not None}

    def describe(self, topic=True):
        parts = []
        if self.topic and topic: parts.append("looking for: " + " ".join(self.topic))
        if self.price_min is not None: parts.append(f"price ≥ {fmt_price(self.price_min)}")
        if self.price_max is not None: parts.append(f"price ≤ {fmt_price(self.price_max)}")
        if self.min_rating is not None: parts.append(f"rating ≥ {self.min_rating:g}")
        if self.stock is not None: parts.append("in stock" if self.stock else "out of stock")
        parts += [f"category: {c}" for c in self.categories]
        parts += [a.label for a in self.attrs]
        if self.sort: parts.append({"price_asc": "cheapest first", "price_desc": "priciest first",
                                    "rating_desc": "best rated first"}[self.sort])
        return " · ".join(parts)


@dataclass
class Reply:
    text: str
    outcome: str                      # results|clarify|not_found|no_match|fact|policy|policy_refusal|need_ref|chat|blocked
    products: list = field(default_factory=list)
    filters: str = ""
    validation: Validation | None = None
    latency_ms: float = 0.0
    cited_ids: list = field(default_factory=list)
    cited_sections: list = field(default_factory=list)
    trace: dict = field(default_factory=dict)

    @property
    def behaviour(self):
        """Coarse label used in reports: answer / clarify / refuse."""
        if self.outcome in ("results", "fact", "policy"):
            return "answer"
        if self.outcome in ("clarify", "need_ref"):
            return "clarify"
        if self.outcome == "chat":
            return "chat"
        return "refuse"


class Assistant:
    def __init__(self, products, sections, embedder, cache_key="catalogue", is_mock=False):
        self.products, self.by_id = products, {p.id: p for p in products}
        self.vocab = Vocab(products)
        self.retriever = Retriever(products, embedder, cache_key)
        self.policy = PolicyAssistant(sections, embedder)
        self.is_mock, self.embedder_name = is_mock, embedder.name

    # ------------------------------------------------------------------ public
    def chat(self, session: Session, message: str) -> Reply:
        t0 = time.perf_counter()
        parsed = parse(message, self.vocab)
        reply = self._route(session, parsed)
        v = validate(reply.text, self.by_id, self.policy.by_label, session.amounts | parsed.user_amounts)
        reply.validation = v
        if not v.ok:                                    # last line of defence
            reply = Reply("I couldn't verify that answer against the catalogue and policy, so I'm not showing it "
                          "rather than risk a wrong claim. Please rephrase your question.", "blocked",
                          trace={"blocked_errors": v.errors}, validation=v)
        reply.filters = session.describe()
        reply.latency_ms = (time.perf_counter() - t0) * 1000
        session.history += [("user", message), ("assistant", reply.text)]
        return reply

    # ------------------------------------------------------------------ routing
    def _route(self, s: Session, p: Parsed) -> Reply:
        has_search = bool(p.topic or p.has_filters or p.sort or p.remove or p.remove_words)
        if p.reset:
            s.clear()
            if not has_search:
                return Reply("Okay, I've cleared your filters. What would you like to find?", "chat")
        if p.greeting and not has_search and not p.ids:
            return Reply("Hi! Ask me about products in our catalogue (e.g. “cotton shirts under ₹1,500”) "
                         "or about returns, shipping and warranty. I only answer from the catalogue and policy.", "chat")
        if p.ids:
            return self._ids_reply(p)
        if p.policy:
            return self._policy_reply(p)
        if p.ordinal is not None or (p.pronoun and (p.fact_words or (s.last and not p.has_filters))):
            ref = self._resolve_ref(s, p)
            if isinstance(ref, Reply):
                return ref
            return self._fact_reply(ref, p)
        if not has_search:
            return Reply("What would you like to find? You can describe a product, a budget, a colour or a category.", "chat")
        self._apply(s, p)
        if s.empty:
            return Reply("Okay. I've removed that. What would you like to look for?", "chat")
        return self._search_reply(s, p)

    # ------------------------------------------------------------------ state
    def _apply(self, s: Session, p: Parsed):
        if "price" in p.remove: s.price_min = s.price_max = None
        if "rating" in p.remove: s.min_rating = None
        if "stock" in p.remove: s.stock = None
        if "category" in p.remove: s.categories = []
        for w in p.remove_words:
            st = stem(w)
            s.attrs = [a for a in s.attrs if st != a.token and w not in {k.split()[0] for k in a.keys}]
            s.topic = [t for t in s.topic if stem(t) != st]
        if p.topic:
            s.topic = list(p.topic)                       # a new subject replaces the old one…
        if p.price_min is not None: s.price_min = p.price_min   # …but a new budget just updates the old one
        if p.price_max is not None: s.price_max = p.price_max
        if p.min_rating is not None: s.min_rating = p.min_rating
        if p.stock is not None: s.stock = p.stock
        if p.categories: s.categories = list(p.categories)
        for a in p.attrs:                                 # a new value for the same attribute replaces the old one
            s.attrs = [o for o in s.attrs if not (o.keys & a.keys)] + [a]
        if p.sort: s.sort = p.sort

    # ------------------------------------------------------------------ product search
    def _search_reply(self, s: Session, p: Parsed) -> Reply:
        found, diag = self.retriever.search(s)
        n = len(found)
        flt = s.describe()
        note = "".join(f"I read “{a}” as “{b}”. " for a, b in p.corrections)
        r = self._search_core(s, p, found, diag, n, flt)
        r.text = note + r.text if note and r.outcome in ("results", "clarify") else r.text
        return r

    def _search_core(self, s, p, found, diag, n, flt):
        if n == 0:
            s.last = []
            if diag and diag["relax"]:
                opts = "; ".join(f"dropping “{lbl}” gives {c} match{'es' if c != 1 else ''}" for _, lbl, c in diag["relax"])
                return Reply(f"No product satisfies all of: {s.describe(topic=False)}. If you relax one constraint — {opts}. "
                             "Which would you like to drop?", "no_match", trace=diag)
            what = " ".join(s.topic) or "that"
            if diag and diag.get("topic_only"):
                return Reply(f"There are {diag['topic_only']} products for “{what}”, but none satisfy all of: {s.describe(topic=False)}. "
                             "Try dropping one or two of those constraints.", "no_match", trace=diag)
            return Reply(f"I couldn't find “{what}” in the supplied catalogue or policy document, so I won't guess or suggest "
                         "something unrelated. Try different words, or tell me the product type, brand or colour you want.",
                         "not_found", trace=diag or {})
        narrowed = sum([s.price_min is not None or s.price_max is not None, s.min_rating is not None,
                        s.stock is not None, bool(s.categories), len(s.attrs) > 0])
        if n > config.CLARIFY_THRESHOLD and narrowed < 2 and not s.sort and not p.force:
            facets = self.retriever.facets(found)
            asks = "; ".join(f"{name}: {', '.join(vals)}" for name, vals in facets)
            ask = f" Which do you want — {asks} — or a budget?" if asks else " Could you tell me a budget, colour or brand?"
            s.last = []
            return Reply(f"I found {n} products that match, which is too many to pick from.{ask} "
                         "(Say “just show me the top ones” to see some now.)", "clarify", trace={"matches": n})
        top = found[:config.TOP_K]
        s.last = [x.id for x in top]
        head = f"Here {'is the best match' if len(top) == 1 else f'are the top {len(top)}'} of {n} matching product{'s' if n != 1 else ''}"
        lines = [head + ":"]
        for i, x in enumerate(top, 1):
            lines.append(f"{i}. **{x.title}** — {fmt_price(x.price)} · {fmt_stock(x.stock)} · {fmt_rating(x.rating)} {cite(x)}")
        if n > len(top):
            lines.append(f"…and {n - len(top)} more. Add a filter (budget, colour, brand) to narrow it down.")
        return Reply("\n".join(lines), "results", top, cited_ids=[x.id for x in top])

    # ------------------------------------------------------------------ specific products
    def _ids_reply(self, p: Parsed) -> Reply:
        found = [self.by_id[self.vocab.ids[i]] for i in p.ids if i in self.vocab.ids]
        missing = [i for i in p.ids if i not in self.vocab.ids]
        parts, prods = [], []
        for i in missing:
            parts.append(f"There is no product with ID “{i}” in the supplied catalogue.")
        if p.policy:
            r = self._policy_reply(p, found)
            parts.append(r.text)
            prods = r.products
        else:
            for x in found:
                parts.append(self._fact_reply(x, p).text)
                prods.append(x)
        outcome = "not_found" if missing and not found else ("policy" if p.policy else "fact")
        return Reply("\n\n".join(parts), outcome, prods, cited_ids=[x.id for x in found])

    def _resolve_ref(self, s: Session, p: Parsed):
        if not s.last:
            return Reply("Which product do you mean? I don't have one selected yet — search first, or give me a product ID.", "need_ref")
        if p.ordinal is not None:
            i = p.ordinal
            if i >= len(s.last) and i != -1:
                return Reply(f"I only showed {len(s.last)} product(s). Which one do you mean?", "need_ref")
            return self.by_id[s.last[i]]
        if len(s.last) == 1:
            return self.by_id[s.last[0]]
        names = ["1st", "2nd", "3rd", "4th", "5th"][:len(s.last)]
        return Reply(f"Which one do you mean — the {' or '.join(names)} of the {len(s.last)} I just showed?", "need_ref")

    def _fact_reply(self, x, p: Parsed) -> Reply:
        lines = [f"**{x.title}** {cite(x)}",
                 f"- Price: {fmt_price(x.price)} {cite(x)}",
                 f"- Availability: {fmt_stock(x.stock)} {cite(x)}",
                 f"- Rating: {fmt_rating(x.rating)} {cite(x)}"]
        if x.category:
            lines.append(f"- Category: {x.category} {cite(x)}")
        asked = [t for t in self._detail_words(p) if t]
        for t in asked:                                   # extra details: answer only if the entry really has it
            hit = [(k, v) for k, v in x.attributes.items() if stem(t) in {stem(w) for w in (k + " " + v).lower().split()}]
            if hit:
                lines += [f"- {k}: {v} {cite(x)}" for k, v in hit]
            elif stem(t) not in {stem(w) for w in x.description.lower().split()}:
                lines.append(f"- “{t}”: not listed in the catalogue entry for this product, so I can't say. {cite(x)}")
        return Reply("\n".join(lines), "fact", [x], cited_ids=[x.id])

    @staticmethod
    def _detail_words(p: Parsed):
        from .nlp import FACT_WORDS
        from .text import STOP
        return [t for t in p.topic if t not in FACT_WORDS and t not in STOP][:3] if (p.ids or p.pronoun or p.ordinal is not None) else []

    # ------------------------------------------------------------------ policy
    def _policy_reply(self, p: Parsed, products=()) -> Reply:
        import re
        query = p.raw
        for i in p.ids:
            query = re.sub(re.escape(i), " ", query, flags=re.I)
        pw = [t for t in p.topic if t in self.vocab.words]
        status, text, labels = self.policy.answer(query, p.policy, pw)
        extra = []
        for x in products:                                 # product-specific terms only if the catalogue lists them
            for k, v in x.attributes.items():
                if any(stem(w) in {stem(t) for t in k.lower().split()} for w in p.policy | {"warranty", "return", "shipping"} if w in k.lower()):
                    extra.append(f"The catalogue lists for **{x.title}**: {k}: {v} {cite(x)}")
        return Reply(text + ("\n\n" + "\n".join(extra) if extra else ""),
                     "policy" if status == "answer" else "policy_refusal", list(products),
                     cited_sections=labels, cited_ids=[x.id for x in products])
