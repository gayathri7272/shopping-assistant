"""Generates a MOCK catalogue + policy for development ONLY.
Every title is a generic item and every ID starts with MOCK-. Replace with the organisers' files
by copying them to data/catalogue.* and data/policy.txt (see README)."""
import json
import random
from pathlib import Path

MOCK = Path(__file__).resolve().parent.parent / "data" / "mock"
random.seed(7)

SPECS = {  # category -> [(item, base price, materials)]
    "Apparel": [("Shirt", 900, ["Cotton", "Linen", "Polyester"]), ("T-Shirt", 500, ["Cotton", "Polyester"]),
                ("Kurta", 1100, ["Cotton", "Silk", "Rayon"]), ("Jeans", 1600, ["Denim", "Cotton"])],
    "Footwear": [("Sneakers", 2200, ["Canvas", "Leather", "Mesh"]), ("Sandals", 700, ["Leather", "Rubber"]),
                 ("Running Shoes", 2800, ["Mesh", "Synthetic"])],
    "Electronics": [("Wireless Headphones", 2500, ["Plastic"]), ("Smartwatch", 3500, ["Plastic", "Metal"]),
                    ("Bluetooth Speaker", 1800, ["Plastic"]), ("Laptop", 42000, ["Metal"])],
    "Home & Kitchen": [("Water Bottle", 400, ["Steel", "Plastic"]), ("Bedsheet", 1200, ["Cotton", "Polyester"]),
                       ("Mixer Grinder", 3200, ["Steel", "Plastic"])],
    "Bags": [("Backpack", 1500, ["Nylon", "Canvas", "Leather"])],
}
COLORS = ["Black", "White", "Blue", "Red", "Green", "Grey"]
BRANDS = ["Acme", "Zenith", "Orbit", "Nova"]
GENDERS = ["Men", "Women", "Unisex"]

products, n = [], 1
for cat, items in SPECS.items():
    for item, base, mats in items:
        for _ in range(14 if item != "Laptop" else 4):
            mat, color, brand = random.choice(mats), random.choice(COLORS), random.choice(BRANDS)
            attrs = {"Brand": brand, "Color": color, "Material": mat}
            if cat in ("Apparel", "Footwear"):
                attrs["Gender"] = random.choice(GENDERS)
            if item == "Laptop":
                attrs["RAM"] = random.choice(["8GB", "16GB"])
            if "Headphones" in item:
                attrs["Warranty"] = "12 months"
            stock = random.choices(["In Stock", "Out of Stock"], [0.8, 0.2])[0]
            products.append({
                "id": f"MOCK-{n:04d}",
                "title": f"{brand} {color} {mat} {item}",
                "description": f"MOCK sample {item.lower()} made of {mat.lower()} in {color.lower()}.",
                "attributes": attrs,
                "price": round(base * random.uniform(0.7, 1.5) / 10) * 10,
                "stock_status": stock,
                "category": cat,
                "rating": random.choice([None, round(random.uniform(3.0, 4.9), 1)]),
            })
            n += 1

(MOCK / "catalogue.json").write_text(json.dumps(products, indent=1, ensure_ascii=False), encoding="utf-8")
(MOCK / "policy.txt").write_text("""R3 MOCK STORE POLICY (SAMPLE TEXT - NOT THE ORGANISERS' POLICY)

1. Returns
Items can be returned within 30 days of delivery if they are unused and in original packaging. Refunds are issued to the original payment method within 7 business days after the item is received. Footwear that has been worn outdoors cannot be returned.

2. Shipping
Standard delivery takes 3 to 5 business days. Orders above ₹999 qualify for free shipping. Orders below ₹999 are charged a shipping fee of ₹49. Express delivery is not available.

3. Warranty
Electronics carry a 12-month manufacturer warranty from the date of delivery. The warranty covers manufacturing defects only and does not cover accidental damage. Apparel and footwear carry no warranty.
""", encoding="utf-8")
print(f"wrote {len(products)} MOCK products")
