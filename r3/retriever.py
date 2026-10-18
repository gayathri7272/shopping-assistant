"""Product retrieval = hard filters (exact, deterministic) + semantic ranking (embeddings),
with a lexical guard so an unrelated product can never be returned."""
import numpy as np

from . import config
from .embedder import encode_cached
from .text import SYN, norm_key, stem, tokens


def product_tokens(p):
    out = tokens(p.title) + tokens(p.category) + tokens(p.description)
    for k, v in p.attributes.items():
        out += tokens(k) + tokens(v)
    return out


class Retriever:
    def __init__(self, products, embedder, cache_key="catalogue"):
        self.products, self.embedder = products, embedder
        n = len(products)
        self.price = np.array([p.price if p.price is not None else np.nan for p in products], dtype=float)
        self.rating = np.array([p.rating if p.rating is not None else np.nan for p in products], dtype=float)
        self.stock = np.array([-1 if p.stock is None else int(p.stock) for p in products])
        self.cats = np.array([p.category for p in products], dtype=object)
        self.ptok = [{stem(t) for t in product_tokens(p)} for p in products]
        self.attr_tok = [{norm_key(k): {stem(t) for t in tokens(v)} for k, v in p.attributes.items()} for p in products]
        self.emb = encode_cached(embedder, [p.text() for p in products], cache_key)
        self._attr_cache = {}

    # ---------- exact filters ----------
    def _attr_mask(self, a):
        key = (a.token, a.keys)
        if key not in self._attr_cache:
            self._attr_cache[key] = np.array(
                [any(a.token in at.get(k, ()) for k in a.keys) for at in self.attr_tok])
        return self._attr_cache[key]

    def mask(self, f, skip=()):
        m = np.ones(len(self.products), dtype=bool)
        with np.errstate(invalid="ignore"):          # NaN (unknown price) never passes a price filter
            if f.price_min is not None and "price" not in skip:
                m &= self.price >= f.price_min
            if f.price_max is not None and "price" not in skip:
                m &= self.price <= f.price_max
            if f.min_rating is not None and "rating" not in skip:
                m &= self.rating >= f.min_rating
        if f.stock is not None and "stock" not in skip:
            m &= self.stock == int(f.stock)
        if f.categories and "category" not in skip:
            m &= np.isin(self.cats, list(f.categories))
        for a in f.attrs:
            if f"attr:{a.label}" not in skip:
                m &= self._attr_mask(a)
        return m

    # ---------- relevance ----------
    def _topic_scores(self, topic):
        """Returns (cosine, covered?) for every product. 'covered' = every word the user typed
        (or a synonym of it) appears in the product text. Numbers must always match exactly."""
        syn = [w for t in topic for w in SYN.get(stem(t), [])]
        q = self.embedder.encode([" ".join(topic + syn)])[0]
        cos = self.emb @ q
        need = [stem(t) for t in topic]
        covered = np.array([all((s in pt) or any(x in pt for x in SYN.get(s, ())) for s in need)
                            for pt in self.ptok])
        return cos, covered

    def relevant(self, topic):
        if not topic:
            return np.ones(len(self.products), dtype=bool), np.zeros(len(self.products))
        cos, covered = self._topic_scores(topic)
        digits_ok = np.array([all(stem(t) in pt for t in topic if any(c.isdigit() for c in t))
                              for pt in self.ptok])
        ok = (covered | (cos >= config.HIGH_COS)) & digits_ok & (cos >= config.MIN_COS)
        return ok, cos

    def search(self, f):
        ok, cos = self.relevant(f.topic)
        m = self.mask(f) & ok
        idx = np.where(m)[0]
        order = self._rank(idx, cos, f)
        diag = None
        if len(idx) == 0:
            diag = self._relax(f, ok)
        return [self.products[i] for i in order], diag

    def _rank(self, idx, cos, f):
        def rat(i): return -(self.rating[i] if not np.isnan(self.rating[i]) else -1)
        def prc(i): return self.price[i] if not np.isnan(self.price[i]) else 1e12
        if f.sort == "price_asc":
            key = lambda i: (prc(i), -cos[i])
        elif f.sort == "price_desc":
            key = lambda i: (-(prc(i) if prc(i) < 1e12 else -1), -cos[i])
        elif f.sort == "rating_desc" or not f.topic:
            key = lambda i: (rat(i), prc(i))
        else:
            key = lambda i: (-round(float(cos[i]), 3), rat(i), self.products[i].id)
        return sorted(idx, key=key)

    def _relax(self, f, ok):
        """When nothing matches: which single filter, if dropped, would give results?"""
        groups = []
        if f.price_min is not None or f.price_max is not None: groups.append(("price", "price limit"))
        if f.min_rating is not None: groups.append(("rating", "rating filter"))
        if f.stock is not None: groups.append(("stock", "stock filter"))
        if f.categories: groups.append(("category", "category filter"))
        groups += [(f"attr:{a.label}", a.label) for a in f.attrs]
        # attribute words (e.g. "cotton") are already enforced by their own filter, so judge the
        # remaining words (the product type) separately to say what exists and what blocks it
        attr_tokens = {a.token for a in f.attrs}
        core = [t for t in f.topic if stem(t) not in attr_tokens]
        ok_core = self.relevant(core)[0] if core else np.ones(len(self.products), dtype=bool)
        out = []
        for key, label in groups:
            n = int((self.mask(f, skip=(key,)) & ok_core).sum())
            if n:
                out.append((key, label, n))
        topic_only = int(ok_core.sum()) if core else None
        return {"relax": out, "topic_only": topic_only}

    def facets(self, products):
        """Options to ask the user about, taken from the matching products themselves."""
        cats = sorted({p.category for p in products if p.category})
        out = []
        if len(cats) > 1:
            out.append(("category", cats[:6]))
        keys = {}
        for p in products:
            for k, v in p.attributes.items():
                keys.setdefault(k, set()).add(v)
        for k, vs in sorted(keys.items(), key=lambda kv: len(kv[1])):
            if 2 <= len(vs) <= 6 and len(out) < 2:
                out.append((k.lower(), sorted(vs)))
        return out
