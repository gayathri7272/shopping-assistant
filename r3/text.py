"""Tiny text helpers shared by every module: tokenising, stemming, synonyms."""
import re


def stem(w: str) -> str:
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("ches", "shes", "sses", "xes", "zes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def tokens(text: str):
    t = str(text).lower().replace("’", "'")
    t = re.sub(r"'s\b", "", t)
    return re.findall(r"[a-z0-9]+", t)


def norm_key(k: str) -> str:
    return " ".join(tokens(k))


# Words that never make a product search more specific (English + romanised Hindi/Telugu filler)
STOP = set("""
i me my we you your it its this that these those the a an and or of in on at to for with from by as is are was be
do does did can could would should will have has had there here some any all just only also too very more most
want need needs show find get give tell let looking look search buy purchase see list suggest recommend
please pls hi hello hey thanks thank ok okay what which who how whats
under below above over than less within upto up max maximum min minimum least around about
rs inr rupee rupees rupaye price cost budget stock available availability rating ratings rated star stars
product products item items one ones something anything thing stuff best top good nice great latest new
stylish comfortable comfy premium quality affordable popular trending
cheap cheapest sasta saste lowest expensive costliest
chahiye chaiye dikhao dikha batao bata mujhe muje hai hain ka ki ke ko se mein me wala wali wale aur kya koi
nahi kam andar ander neeche tak dena do ho hoga
naku kavali kavalani cheppu lo lopu enti undi unda ledu oka konchem chupinchu cheyyi vundi
""".split())

SYN_RAW = {
    "clothes": ["clothing", "apparel", "shirt", "tshirt", "kurta", "jeans", "dress", "hoodie", "jacket", "trouser"],
    "clothing": ["clothes", "apparel", "shirt", "tshirt", "kurta", "jeans", "dress", "hoodie", "jacket", "trouser"],
    "apparel": ["clothes", "clothing", "shirt", "tshirt", "kurta", "jeans"],
    "kapde": ["clothes", "clothing", "apparel", "shirt", "kurta", "jeans"],
    "kapda": ["clothes", "clothing", "apparel", "shirt", "kurta", "jeans"],
    "battalu": ["clothes", "clothing", "apparel", "shirt", "kurta", "jeans"],
    "shoes": ["footwear", "sneakers", "sandals", "slippers", "boots", "loafers"],
    "footwear": ["shoes", "sneakers", "sandals", "slippers", "boots"],
    "joota": ["shoes", "footwear", "sneakers"], "juta": ["shoes", "footwear", "sneakers"],
    "bootlu": ["shoes", "footwear", "sneakers"],
    "chappal": ["sandals", "slippers", "footwear"],
    "phone": ["mobile", "smartphone"], "mobile": ["phone", "smartphone"], "smartphone": ["phone", "mobile"],
    "laptop": ["notebook"], "tv": ["television"], "fridge": ["refrigerator"],
    "headphones": ["earphones", "earbuds", "headset"], "earphones": ["headphones", "earbuds"],
    "earbuds": ["headphones", "earphones"],
    "watch": ["smartwatch", "wristwatch"], "bag": ["backpack", "handbag", "luggage"],
    "tshirt": ["shirt", "tee"], "tee": ["shirt", "tshirt"],
    "men": ["mens", "male", "gents"], "women": ["womens", "ladies", "female"],
    "ladies": ["women"], "gents": ["men"],
}
SYN = {stem(k): [stem(s) for s in v] for k, v in SYN_RAW.items()}
