# =============================================================================
# Selene Dreams — test_catalog.py v1.0 (2026-08-26)
# One-shot check: can the SYSTEM USER token see the product catalog and
# search products? Run on the Mac:  python3 test_catalog.py
# Read-only — makes no posts, changes nothing.
# =============================================================================
import sys, requests, config

IG_USER_ID = "17841451177142651"
GRAPH = "https://graph.facebook.com/v21.0"

def main():
    token = config._ENV.get("IG_ACCESS_TOKEN", "")
    if not token:
        sys.exit("IG_ACCESS_TOKEN missing from .env")

    r = requests.get(f"{GRAPH}/{IG_USER_ID}/available_catalogs",
                     params={"fields": "catalog_id,catalog_name,product_count",
                             "access_token": token}, timeout=30)
    print("available_catalogs HTTP", r.status_code)
    print(r.text[:800])
    if r.status_code != 200:
        print("\n=> Token cannot see catalogs yet. Likely fixes: assign the "
              "catalog to the system user in Business Manager (Assigned assets "
              "> Catalogs), or regenerate the token with catalog_management + "
              "instagram_shopping_tag_products.")
        return
    cats = r.json().get("data", [])
    if not cats:
        print("\n=> No catalog linked to this IG account.")
        return
    cid = cats[0]["catalog_id"]
    q = sys.argv[1] if len(sys.argv) > 1 else "linen"
    r2 = requests.get(f"{GRAPH}/{IG_USER_ID}/catalog_product_search",
                      params={"catalog_id": cid, "q": q,
                              "access_token": token}, timeout=30)
    print(f"\ncatalog_product_search q='{q}' HTTP", r2.status_code)
    print(r2.text[:1200])
    if r2.status_code == 200:
        print("\n=> TAGGING PREREQS OK. Send this output to Claude.")

if __name__ == "__main__":
    main()
