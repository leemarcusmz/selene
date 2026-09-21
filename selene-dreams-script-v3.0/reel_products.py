"""
reel_products.py — let Marcus tell the lane what is in the video
=============================================================================
VERSION 1.1 — 2026-09-10

THE PROBLEM
    The vision pass looked at real Gauze Blanket footage and honestly reported
    product_guess "unclear". It was right to: a crinkled beige cloth on a sofa
    is not identifiable from frames alone. But Marcus KNOWS what it is, and
    without a way to say so the lane permanently refuses to name the product,
    drops "Meet the Product", and blocks every product hashtag — on his best
    footage.

THE FIX, WITH NO NEW TOOLING
    Put the product in the Drive FILENAME. Renaming a file in Drive takes two
    taps on a phone, which is the whole point — the lane must stay a
    "upload it and forget it" system.

        DJI_20250705172022_0090_D_1.MP4        -> unclear, as before
        Gauze_Blanket_Soft-Maple.MP4           -> confirmed
        gauze blanket - sofa shake.mp4         -> confirmed
        linen duvet set desert sand.mov        -> confirmed, with colourway

    A filename match is treated as GROUND TRUTH and overrides the vision pass,
    because Marcus was in the room and the model was not.

THE VOCABULARY IS THE REAL CATALOGUE
    Taken from the actual filenames in Drive "01. Product Photos"
    (Fabric_ProductType_Variant.jpg), not invented. That is the same naming the
    generation lane resolves against.

    NOTE THE KNOWN TRAP: "Gauze Blanket" and "Cooling Blanket" are
    Fabric + Type, NOT atomic fabric names. Treating "Cooling Blanket" as a
    fabric is exactly the bug that ERRORs a generation row every time one is
    picked (selene-generation-gotchas). This parser reads fabric and type
    SEPARATELY, so it cannot make that mistake.

CHANGELOG
    1.1  2026-09-10  The Cooling product is titled COOLING COMFORTER on the
                     site, but the product-photo filenames say Cooling_Blanket.
                     Both spellings now parse (an internal filename is a fine
                     thing to type) and both resolve to the SITE name, because
                     that is what copy has to say. Verified off the product page
                     2026-09-10; recorded in claims_edu.md v3.
    1.0  2026-09-09  First build.
=============================================================================
"""

import re

FABRICS = ["Linen", "Gauze", "Cooling", "Silk", "Tencel", "Sateen", "Percale"]

# Canonical type name -> the spellings that may appear in a filename.
# Canonical SITE name -> spellings that may appear in a filename.
TYPES = {
    "Comforter":  ["comforter"],
    "Duvet Set":  ["duvet-set", "duvet set", "duvetset", "duvet"],
    "Sheet Set":  ["sheet-set", "sheet set", "sheetset", "sheets", "sheet"],
    "Blanket":    ["blanket", "throw"],
    "Pillow Case": ["pillow-case", "pillow case", "pillowcase", "pillowcases"],
    "Eye Mask":   ["eye-mask", "eye mask", "eyemask", "sleep mask", "sleepmask"],
}

VARIANTS = [
    "Alabaster White", "Desert Sand", "Stone Sage", "Terracotta Blush",
    "Soft Maple", "Shadow Gray", "Cream White", "Silver Mist", "Ocean Breeze",
    "Icy White", "Driftwood", "Herb Sage", "Ash Gray", "Dove Gray",
    "Frost White", "Deep Ocean", "Stone Taupe", "Olive Sage", "Warm Taupe",
    "Pewter Gray",
]

# Which fabrics each type actually ships in, so an impossible combination in a
# filename is not silently accepted.
VALID_PAIRS = {
    ("Gauze", "Blanket"),
    ("Cooling", "Blanket"), ("Cooling", "Comforter"),
    ("Linen", "Duvet Set"), ("Linen", "Sheet Set"),
    ("Tencel", "Duvet Set"), ("Tencel", "Sheet Set"),
    ("Sateen", "Duvet Set"), ("Sateen", "Sheet Set"),
    ("Percale", "Duvet Set"), ("Percale", "Sheet Set"),
    ("Silk", "Pillow Case"), ("Silk", "Eye Mask"),
}


def _norm(text):
    """Filenames use _ - . and spaces interchangeably. Flatten them."""
    text = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", text)          # drop extension
    text = re.sub(r"[_\-.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def parse(filename):
    """Read a product declaration out of a filename.

    Returns a dict, or None when the filename declares nothing. Never guesses:
    a bare fabric or a bare type is not a product.
    """
    text = _norm(filename)

    fabric = next((f for f in FABRICS
                   if re.search(rf"\b{f.lower()}\b", text)), None)

    ptype = None
    for canonical, spellings in TYPES.items():
        for spelling in sorted(spellings, key=len, reverse=True):
            if re.search(rf"\b{re.escape(spelling)}\b", text):
                ptype = canonical
                break
        if ptype:
            break

    if not fabric or not ptype:
        return None
    if (fabric, ptype) not in VALID_PAIRS:
        return None

    variant = next((v for v in VARIANTS if v.lower() in text), None)

    # Say what the SITE says. "Cooling Blanket" is an internal photo-filename
    # convention; the product page titles it Cooling Comforter, and copy must
    # use the customer-facing name.
    if fabric == "Cooling":
        ptype = "Comforter"

    name = f"{fabric} {ptype}"
    return {
        "fabric": fabric,
        "product_type": ptype,
        "variant": variant,
        "name": f"{name} in {variant}" if variant else name,
        "source": "filename",
    }


def apply_to_description(description, filename):
    """Overwrite the vision pass's guess when the filename declares a product.

    Ground truth beats a model looking at six frames. Returns (description,
    product_or_None) — the description is mutated in place for the caller.
    """
    product = parse(filename)
    if not product:
        return description, None

    description["product_guess"] = product["name"]
    description["fabric_guess"] = product["fabric"].lower()
    description["product_confirmed"] = True
    description["product_source"] = "filename"
    return description, product
