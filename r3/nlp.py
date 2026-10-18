"""Turns a user message into structured constraints. Pure rules (regex + fuzzy spelling),
so every decision can be explained and nothing is guessed by a model."""
import difflib
import re
from dataclasses import dataclass, field

from .text import STOP, norm_key, stem, tokens

POLICY_KINDS = {
    "return": {"return", "refund", "exchange", "replace", "replacement", "money"},
    "shipping": {"ship", "shipping", "delivery", "deliver", "dispatch", "courier", "tracking", "shipped"},
    "warranty": {"warranty", "guarantee", "repair", "defect", "defective"},
    "cancel": {"cancel", "cancellation"},
    "policy": {"policy", "policies"},
}
POLICY_STEMS = {stem(w): k for k, ws in POLICY_KINDS.items() for w in ws}
FACT_WORDS = {"price", "cost", "stock", "available", "availability", "rating", "rated", "review", "reviews",
              "category", "mrp", "much", "detail", "details", "specs", "specification", "about"}
ORDINALS = {"first", "1st", "second", "2nd", "third", "3rd", "last", "one", "ones"}
GREETINGS = {"hi", "hello", "hey", "thanks", "thank", "namaste", "hii", "helo", "ok", "okay", "bye"}


@dataclass
class AttrFilter:
    token: str          # stemmed value, e.g. "cotton"
    keys: frozenset     # normalised attribute names it may live under, e.g. {"material"}
    label: str          # for display, e.g. "material: cotton"


@dataclass
class Parsed:
    raw: str
    ids: list = field(default_factory=list)
    reset: bool = False
    remove: set = field(default_factory=set)         # price / rating / stock / category
    remove_words: list = field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    min_rating: float | None = None
    stock: bool | None = None
    categories: list = field(default_factory=list)
    attrs: list = field(default_factory=list)
    topic: list = field(default_factory=list)
    sort: str | None = None
    policy: set = field(default_factory=set)
    fact_words: set = field(default_factory=set)
    ordinal: int | None = None                       # 0,1,2.. or -1 for "last"
    pronoun: bool = False
    greeting: bool = False
    force: bool = False                              # "just show me anyway"
    user_amounts: set = field(default_factory=set)
    corrections: list = field(default_factory=list)   # [(typed, understood)]

    @property
    def has_filters(self):
        return any([self.price_min is not None, self.price_max is not None, self.min_rating is not None,
                    self.stock is not None, self.categories, self.attrs])


class Vocab:
    """Everything the catalogue teaches us about words: spelling, categories, attribute values, ID shapes."""

    def __init__(self, products):
        from .retriever import product_tokens
        self.id_shapes, self.ids = set(), {}
        self.words, self.cat_stems, self.attr_index = set(), {}, {}
        for p in products:
            self.ids[p.id.upper()] = p.id
            self.id_shapes.add(self._shape(p.id))
            for t in product_tokens(p):
                if len(t) >= 3 and not t.isdigit():
                    self.words.add(t)
            if p.category and p.category not in self.cat_stems:
                leaf = re.split(r"[>/|]", p.category)[-1]
                self.cat_stems[p.category] = {stem(t) for t in tokens(leaf) if len(t) >= 3 and t != "and"}
            for k, v in p.attributes.items():
                ws = tokens(v)
                if not ws or len(ws) > 3:
                    continue
                for w in ws:
                    s = stem(w)
                    if len(w) < 2 or w.isdigit() or s in STOP or w in STOP:
                        continue
                    e = self.attr_index.setdefault(s, {"keys": set(), "raw": w})
                    e["keys"].add(norm_key(k))
        self._by_len = {}
        for w in self.words:
            self._by_len.setdefault(len(w), []).append(w)
        self._cache = {}

    @staticmethod
    def _shape(s):
        return re.sub(r"[A-Za-z]+", "A", re.sub(r"\d+", "9", s.upper()))

    def correct(self, tok):
        """Fix small typos using words that really exist in the catalogue (same first letter)."""
        if tok in self.words or tok in STOP or tok.isdigit() or len(tok) < 4:
            return tok
        if tok in self._cache:
            return self._cache[tok]
        limit = 1 if len(tok) <= 7 else 2          # max typos allowed
        cands = [w for L in range(len(tok) - limit, len(tok) + limit + 1) for w in self._by_len.get(L, [])
                 if w[0] == tok[0] and _lev(tok, w) <= limit]
        best = max(cands, key=lambda w: difflib.SequenceMatcher(None, tok, w).ratio()) if cands else tok
        self._cache[tok] = best
        return best


def _lev(a, b):
    """Edit distance (insert/delete/substitute), small and dependency-free."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


NUM = r"(\d+(?:\.\d+)?)\s*(k\b)?"
CUR = r"(?:rs\.?|inr|₹|rupees?|rupaye)?\s*"
CUR_REQ = r"(?:rs\.?|inr|₹|rupees?|rupaye)\s*"
MAXW = r"(?:under|below|less than|lesser than|within|upto|up to|max(?:imum)?|not more than|no more than|at most|cheaper than|budget(?: is| of)?)"
MINW = r"(?:over|above|more than|at least|min(?:imum)?|starting from|greater than)"
SUFFIX_MAX = r"(?:ke andar|ke ander|ke neeche|se kam|tak|lopu|lo|mein|me|or less|or below|and below|max)\b"
SUFFIX_MIN = r"(?:se zyada|se jyada|or more|or above|and above|plus)\b"


def _n(num, k):
    return float(num) * (1000 if k else 1)


def _grab(pattern, text):
    m = re.search(pattern, text)
    if m:
        text = text[:m.start()] + " " + text[m.end():]
    return m, text


def parse(message: str, vocab: Vocab) -> Parsed:
    p = Parsed(raw=message)
    low = message.lower().replace("’", "'")
    low = re.sub(r"(?<=\d),(?=\d{3}\b)", "", low)
    all_tokens = tokens(low)
    st = {stem(t) for t in all_tokens}

    p.greeting = bool(all_tokens) and all(t in GREETINGS or t in STOP for t in all_tokens) and any(t in GREETINGS for t in all_tokens)
    RESET = r"\b(start over|reset|new search|clear (?:everything|all|filters)|forget everything)\b"
    if re.search(RESET, low):
        p.reset = True
        low = re.sub(RESET, " ", low)
    if re.search(r"\b(just show|show anyway|show me anyway|any of them|show top|top results|show all)\b", low):
        p.force = True

    # --- product IDs (shape learned from the real catalogue) ---
    numeric_ids = vocab.id_shapes == {"9"}
    for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-]*[A-Za-z0-9]", message):
        sh = Vocab._shape(tok)
        if sh in vocab.id_shapes and not (numeric_ids and sh == "9"):
            p.ids.append(tok.upper())
            low = re.sub(re.escape(tok.lower()), " ", low)
    if numeric_ids:
        for m in re.finditer(r"(?:\bid|\bsku|\bproduct|\bitem|#)\s*:?\s*(\d{3,})", low):
            p.ids.append(m.group(1))
        low = re.sub(r"(?:\bid|\bsku|\bproduct|\bitem|#)\s*:?\s*\d{3,}", " ", low)
    p.ids = list(dict.fromkeys(p.ids))

    # --- removing constraints ("forget the budget") ---
    rm = r"(?:remove|drop|forget|ignore|skip|clear|cancel)"
    m, low = _grab(rf"\b{rm}\s+(?:the\s+)?(?:price|budget|cost)(?:\s+(?:limit|filter|constraint|cap))?\b|\bno\s+(?:price|budget)\s+limit\b|\bany\s+(?:price|budget)\b|\b(?:price|budget)\s+(?:doesn'?t|does not)\s+matter\b", low)
    if m: p.remove.add("price")
    m, low = _grab(rf"\b{rm}\s+(?:the\s+)?(?:rating|stars?)(?:\s+(?:limit|filter))?\b|\bany\s+rating\b", low)
    if m: p.remove.add("rating")
    m, low = _grab(rf"\b{rm}\s+(?:the\s+)?(?:stock|availability)(?:\s+filter)?\b|\bany\s+availability\b", low)
    if m: p.remove.add("stock")
    m, low = _grab(rf"\b{rm}\s+(?:the\s+)?category(?:\s+filter)?\b|\bany\s+category\b", low)
    if m: p.remove.add("category")
    for m in re.finditer(rf"\b{rm}\s+(?:the\s+)?([a-z]+)\b", low):
        p.remove_words.append(m.group(1))
    low = re.sub(rf"\b{rm}\s+(?:the\s+)?[a-z]+\b", " ", low)
    for m in re.finditer(r"\bany\s+(colou?r|material|brand|gender)\b", low):
        p.remove_words.append(m.group(1).replace("colour", "color"))
    low = re.sub(r"\bany\s+(colou?r|material|brand|gender)\b", " ", low)

    # --- rating ---
    m, low = _grab(r"(\d(?:\.\d)?)\s*\+?\s*(?:stars?|star rating)(?:\s*(?:and above|or above|and up|\+|plus|or more))?|(?:rated|ratings?)\s*(?:of|above|over|at least|>=|more than|min(?:imum)?)?\s*(\d(?:\.\d)?)\s*\+?", low)
    if m:
        p.min_rating = float(m.group(1) or m.group(2))

    # --- price ---
    m, low = _grab(rf"between\s*{CUR}{NUM}\s*(?:and|to|-|&)\s*{CUR}{NUM}|{CUR_REQ}{NUM}\s*(?:to|-)\s*{CUR}{NUM}", low)
    if m:
        a, b = _n(m.group(1), m.group(2)), _n(m.group(3), m.group(4))
        p.price_min, p.price_max = min(a, b), max(a, b)
    else:
        m, low = _grab(rf"{MAXW}\s*{CUR}{NUM}", low)
        if m:
            p.price_max = _n(m.group(1), m.group(2))
        m, low = _grab(rf"{CUR}{NUM}\s*{SUFFIX_MAX}", low)
        if m and p.price_max is None:
            p.price_max = _n(m.group(1), m.group(2))
        m, low = _grab(rf"{MINW}\s*{CUR}{NUM}", low)
        if m:
            p.price_min = _n(m.group(1), m.group(2))
        m, low = _grab(rf"{CUR}{NUM}\s*{SUFFIX_MIN}", low)
        if m and p.price_min is None:
            p.price_min = _n(m.group(1), m.group(2))
        if p.price_max is None and p.price_min is None:   # a bare "₹2000" / "2000 rupees" means a budget
            m, low = _grab(rf"(?:rs\.?|inr|₹)\s*{NUM}|{NUM}\s*(?:rupees?|rupaye|rs\b|inr\b)", low)
            if m:
                g = [x for x in m.groups() if x is not None]
                p.price_max = _n(g[0], g[1] if len(g) > 1 else None)
    p.user_amounts = {x for x in (p.price_min, p.price_max) if x is not None}

    # --- stock ---
    if re.search(r"out of stock|sold out", low):
        p.stock = False
    elif re.search(r"in[ -]?stock|available|stock (?:mein|lo)", low):
        p.stock = True

    # --- sort words ---
    if re.search(r"\b(cheap|cheapest|sasta|saste|lowest price|budget[- ]friendly|affordable)\b", low):
        p.sort = "price_asc"
    elif re.search(r"\b(expensive|costliest|highest price|most expensive)\b", low):
        p.sort = "price_desc"
    elif re.search(r"\b(best|top rated|highest rated|best rated)\b", low):
        p.sort = "rating_desc"

    # --- who is asking about what ---
    for t in all_tokens:
        if stem(t) in POLICY_STEMS:
            p.policy.add(POLICY_STEMS[stem(t)])
    p.fact_words = {t for t in all_tokens if t in FACT_WORDS}
    om = re.search(r"\b(first|1st|second|2nd|third|3rd|last)\b", low)
    if om:
        p.ordinal = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "last": -1}[om.group(1)]
    p.pronoun = bool(re.search(r"\b(it|its|this one|that one|this|that)\b", low)) and not p.ids

    # --- topic words, with spelling repair ---
    topic = []
    for t in tokens(low):
        if t in STOP or (len(t) == 1 and not t.isdigit()):
            continue
        if t in POLICY_STEMS or stem(t) in POLICY_STEMS:
            continue
        if p.ordinal is not None and t in ORDINALS:
            continue
        fixed = vocab.correct(t)
        if fixed != t:
            p.corrections.append((t, fixed))
        topic.append(fixed)
    # category + attribute filters come from words that really exist in the catalogue
    tstems = {stem(t) for t in topic}
    for cat, cs in vocab.cat_stems.items():
        if cs and cs <= tstems:
            p.categories.append(cat)
    seen = set()
    for t in topic:
        s = stem(t)
        if s in vocab.attr_index and s not in seen:
            seen.add(s)
            e = vocab.attr_index[s]
            key = sorted(e["keys"])[0]
            p.attrs.append(AttrFilter(s, frozenset(e["keys"]), f"{key}: {e['raw']}"))
    p.topic = list(dict.fromkeys(topic))
    return p
