"""Load the catalogue and the policy document. Tolerant of different column names,
but it never invents values: anything missing stays None and is shown as 'not listed'."""
import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ALIASES = {
    "id": ("id", "product_id", "productid", "sku", "pid", "item_id"),
    "title": ("title", "name", "product_name", "product_title"),
    "description": ("description", "desc", "details"),
    "attributes": ("attributes", "attrs", "specs", "specifications", "features"),
    "price": ("price", "mrp", "price_inr", "selling_price", "cost"),
    "stock": ("stock_status", "stock", "in_stock", "availability", "instock"),
    "category": ("category", "product_category", "categories"),
    "rating": ("rating", "ratings", "avg_rating", "average_rating", "stars"),
}
IN_STOCK = {"in stock", "instock", "in_stock", "true", "1", "yes", "available", "y"}
OUT_STOCK = {"out of stock", "outofstock", "out_of_stock", "false", "0", "no", "unavailable", "sold out", "n"}


@dataclass
class Product:
    id: str
    title: str
    description: str
    category: str
    price: float | None
    stock: bool | None          # None = not listed
    rating: float | None
    attributes: dict = field(default_factory=dict)

    def text(self) -> str:
        attrs = " ".join(f"{k} {v}" for k, v in self.attributes.items())
        return f"{self.title}. {self.category}. {attrs}. {self.description}"


@dataclass
class Section:
    label: str    # exactly what we cite, e.g. "2. Shipping"
    text: str


def _get(rec: dict, key: str):
    low = {str(k).strip().lower(): v for k, v in rec.items()}
    for a in ALIASES[key]:
        if a in low and low[a] not in (None, ""):
            return low[a]
    return None


def _price(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(v))
    return float(m.group(0).replace(",", "")) if m else None


def _stock(v):
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in IN_STOCK:
        return True
    if s in OUT_STOCK:
        return False
    return None


def _rating(v):
    if isinstance(v, dict):
        v = v.get("average") or v.get("avg") or v.get("rating")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _attrs(v):
    if v is None:
        return {}
    if isinstance(v, dict):
        return {str(k): str(x) for k, x in v.items() if x not in (None, "")}
    s = str(v).strip()
    if s.startswith("{"):
        try:
            return {str(k): str(x) for k, x in json.loads(s).items()}
        except json.JSONDecodeError:
            pass
    out = {}
    for part in re.split(r"[;\n|]", s):
        if ":" in part:
            k, x = part.split(":", 1)
            if k.strip() and x.strip():
                out[k.strip()] = x.strip()
    return out


def _to_product(rec: dict) -> Product | None:
    pid, title = _get(rec, "id"), _get(rec, "title")
    if pid is None or title is None:
        return None
    return Product(
        id=str(pid).strip(), title=str(title).strip(),
        description=str(_get(rec, "description") or "").strip(),
        category=str(_get(rec, "category") or "").strip(),
        price=_price(_get(rec, "price")), stock=_stock(_get(rec, "stock")),
        rating=_rating(_get(rec, "rating")), attributes=_attrs(_get(rec, "attributes")),
    )


def load_catalogue(path) -> list[Product]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Catalogue not found: {path}")
    if path.suffix == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            records = list(csv.DictReader(f))
    elif path.suffix == ".jsonl":
        records = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = next((v for v in data.values() if isinstance(v, list)), [])
        records = data
    seen, products = set(), []
    for r in records:
        p = _to_product(r)
        if p and p.id not in seen:
            seen.add(p.id)
            products.append(p)
    if not products:
        raise ValueError(f"No usable products in {path}. Check the column names in data_loader.ALIASES.")
    return products


HEAD = re.compile(r"^\s*(?:#{1,4}\s+(.+)|((?:[Ss]ection\s+)?\d+(?:\.\d+)*[.):]?\s+[A-Za-z].*)|([A-Z][A-Z0-9 &/,'-]{3,60}:?))\s*$")


def load_policy(path) -> list[Section]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Policy document not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    sections, label, buf = [], "Preamble", []

    def flush():
        body = " ".join(" ".join(buf).split())
        if body:
            sections.append(Section(label, body))

    for line in lines:
        m = HEAD.match(line)
        is_head = bool(m) and len(line.strip()) < 80 and not line.rstrip().endswith((".", ",", ";"))
        if is_head:
            flush()
            label, buf = (m.group(1) or m.group(2) or m.group(3)).strip().rstrip(":"), []
        else:
            buf.append(line.strip())
    flush()
    if len(sections) > 1 and sections[0].label == "Preamble":
        sections = sections[1:]
    if len(sections) == 1 and sections[0].label == "Preamble":   # no headings at all: split by paragraph
        paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")) if p.strip()]
        sections = [Section(f"Paragraph {i + 1}", p) for i, p in enumerate(paras)]
    return sections
