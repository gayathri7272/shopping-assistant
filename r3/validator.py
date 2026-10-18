"""The safety net. Before ANY answer is shown, every price, stock status, rating, product ID,
policy citation and policy quote in it is re-checked against the catalogue and policy text.
If anything fails, the answer is blocked."""
import re
from dataclasses import dataclass, field

PRICE_RE = re.compile(r"₹\s?([\d,]+(?:\.\d+)?)")
ID_RE = re.compile(r"\[ID ([^\]]+)\]")
POL_RE = re.compile(r"\[Policy: ([^\]]+)\]")
STOCK_RE = re.compile(r"\b(In stock|Out of stock)\b")
RATING_RE = re.compile(r"★\s?(\d(?:\.\d)?)")
QUOTE_RE = re.compile(r"“([^”]+)”")


def _norm(s):
    return " ".join(re.sub(r"[“”\"']", "", s.lower()).split())


@dataclass
class Validation:
    ok: bool = True
    errors: list = field(default_factory=list)
    hallucinated_prices: int = 0
    uncited_claims: int = 0
    claims_checked: int = 0


def validate(text, products_by_id, sections_by_label, user_amounts=()) -> Validation:
    v = Validation()
    for line in text.splitlines():
        ids, pols = ID_RE.findall(line), POL_RE.findall(line)
        prices = [float(x.replace(",", "")) for x in PRICE_RE.findall(line)]
        stocks, ratings = STOCK_RE.findall(line), RATING_RE.findall(line)
        # only policy block-quote lines ("> “…”") are treated as quoted policy evidence
        quotes = QUOTE_RE.findall(line) if line.lstrip().startswith(">") else []

        cited = []
        for i in ids:
            if i in products_by_id:
                cited.append(products_by_id[i])
            else:
                v.errors.append(f"cited product ID not in catalogue: {i}")
        cited_secs = []
        for l in pols:
            if l in sections_by_label:
                cited_secs.append(sections_by_label[l])
            else:
                v.errors.append(f"cited policy section does not exist: {l}")

        allowed = {p.price for p in cited if p.price is not None} | set(user_amounts)
        for s in cited_secs:
            allowed |= {float(x.replace(",", "")) for x in PRICE_RE.findall(s.text)}
            allowed |= {float(x) for x in re.findall(r"₹\s?(\d+)", s.text)}
        for pr in prices:
            v.claims_checked += 1
            if pr not in allowed:
                v.hallucinated_prices += 1
                v.errors.append(f"price ₹{pr:g} is not supported by the cited evidence")
        for st in stocks:
            v.claims_checked += 1
            if not cited:
                v.uncited_claims += 1; v.errors.append("stock status without a product citation"); continue
            want = {True: "In stock", False: "Out of stock"}.get(cited[0].stock)
            if want != st:
                v.errors.append(f"stock status '{st}' does not match catalogue ({want or 'not listed'})")
        for r in ratings:
            v.claims_checked += 1
            if not cited:
                v.uncited_claims += 1; v.errors.append("rating without a product citation"); continue
            if cited[0].rating is None or abs(float(r) - cited[0].rating) > 0.051:
                v.errors.append(f"rating ★{r} does not match catalogue")
        for q in quotes:
            v.claims_checked += 1
            if not cited_secs:
                v.uncited_claims += 1; v.errors.append("policy quote without a section citation"); continue
            if not any(_norm(q) in _norm(s.text) for s in cited_secs):
                v.errors.append("quoted policy text not found in the cited section")
        if prices and not cited and not cited_secs and not all(p in set(user_amounts) for p in prices):
            v.uncited_claims += 1
    v.ok = not v.errors
    return v
