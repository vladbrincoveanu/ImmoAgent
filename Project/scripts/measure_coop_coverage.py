"""Success-metric instrument: how many co-op units exist, and where the rest went.

Two views:

* **stored** — what is in MongoDB now, by bautraeger/source, plus the identity
  health counters (rows with/without coop_uid, distinct uids vs docs).
* **funnel** — with ``--live``, re-runs the adapters and counts each unit at
  every stage (parsed → rent/Wien-filtered → validated → upserted → renderable),
  so a loss is attributable to a stage instead of guessed at.

The funnel is the before/after evidence for the identity fix: before it, the
mygewo crawl parsed ~58 Wien rentals and only 17 reached the page, the
difference showing up entirely as ``duplicate`` upserts.
"""
import argparse
import datetime
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Integration.mongodb_handler import MongoDBHandler  # reuse handler, no raw queries

# Mirrors dashboard/app/coop/page.tsx BASE_QUERY — the set the /coop page renders.
# Kept here so "stored" and "what the user actually sees" are separate numbers.
RENDERABLE = {
    "is_genossenschaft": True,
    "url_is_valid": {"$ne": False},
    "coop_source": {"$ne": "willhaben"},
    "buyable": False,
    "bezirk": {"$regex": r"^1\d{3}$"},
    "$or": [{"area_m2": None}, {"area_m2": {"$gte": 15}}],  # MIN_LIVABLE_AREA_M2
}


def stored_report(coll) -> list:
    total = coll.count_documents({"is_genossenschaft": True})
    renderable = coll.count_documents(RENDERABLE)
    with_uid = coll.count_documents({"is_genossenschaft": True, "coop_uid": {"$type": "string"}})
    distinct_uid = len(coll.distinct("coop_uid", {"is_genossenschaft": True,
                                                 "coop_uid": {"$type": "string"}}))
    unique_fp = len(coll.distinct("content_fingerprint_xsrc",
                                  {"is_genossenschaft": True,
                                   "content_fingerprint_xsrc": {"$exists": True}}))
    by_bt = list(coll.aggregate([
        {"$match": {"is_genossenschaft": True}},
        {"$group": {"_id": {"bt": "$bautraeger", "src": "$coop_source"}, "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ]))
    lines = [
        f"total co-op docs: {total}",
        f"renderable on /coop: {renderable}",
        f"with coop_uid: {with_uid} (distinct {distinct_uid})"
        + ("  ⚠️ uid collision" if distinct_uid != with_uid else ""),
        f"without coop_uid: {total - with_uid}",
        f"distinct xsrc fingerprints: {unique_fp}",
        "",
        "by bautraeger/source:",
    ]
    lines += [f"  {r['_id'].get('bt')} / {r['_id'].get('src')}: {r['n']}" for r in by_bt]
    return lines


def funnel_report(handler) -> list:
    """Re-crawl and count every stage. Writes to the DB (it upserts), which is
    the point: the upsert verdict per unit IS the measurement."""
    from dataclasses import asdict
    from Application.scraping import genossenschaft_scraper as coop
    from run_coop import _to_doc, poll_source

    lines, grand = [], Counter()
    for name, cfg in coop.SOURCES.items():
        try:
            listings = poll_source(name, cfg, handler)
        except Exception as e:
            lines.append(f"  {name}: ADAPTER FAILED — {e}")
            continue
        outcomes = Counter()
        by_builder = {}
        for listing in listings:
            verdict = handler.upsert_coop_listing(_to_doc(listing))
            outcomes[verdict] += 1
            by_builder.setdefault(listing.bautraeger or "?", Counter())[verdict] += 1
        grand.update(outcomes)
        lines.append(f"  {name}: parsed={len(listings)} " + " ".join(
            f"{k}={outcomes[k]}" for k in ("inserted", "updated", "duplicate", "invalid", "error")))
        for builder, c in sorted(by_builder.items(), key=lambda kv: -sum(kv[1].values())):
            dup = f"  ⚠️ {c['duplicate']} dropped as duplicate" if c["duplicate"] else ""
            lines.append(f"      {builder}: {sum(c.values())} parsed{dup}")
    lines.insert(0, "funnel (parsed → upsert verdict):")
    lines.append("  TOTAL: " + " ".join(
        f"{k}={grand[k]}" for k in ("inserted", "updated", "duplicate", "invalid", "error")))
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true",
                    help="re-crawl the adapters and print the per-stage funnel (writes upserts)")
    args = ap.parse_args()

    mongo = MongoDBHandler()
    if mongo.collection is None:
        print("❌ No MongoDB connection")
        raise SystemExit(1)

    stamp = datetime.date.today().isoformat()
    lines = [f"# Co-op coverage {stamp}"]
    if args.live:
        lines += funnel_report(mongo) + [""]
    lines += stored_report(mongo.collection)
    report = "\n".join(lines)
    print(report)
    os.makedirs("Project/log", exist_ok=True)
    with open(f"Project/log/coop_coverage_{stamp}.txt", "w", encoding="utf-8") as f:
        f.write(report)
    mongo.close()


if __name__ == "__main__":
    main()
