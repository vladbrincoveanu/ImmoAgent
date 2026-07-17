"""Success-metric instrument: count unique deduped co-op units live now,
broken down by bautraeger + coop_source. Compares against a manual MyGEWO
same-day spot-check (no MyGEWO scraping in v1)."""
import os, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Integration.mongodb_handler import MongoDBHandler  # reuse handler, no raw queries

def main():
    mongo = MongoDBHandler()
    coll = mongo.collection
    total = coll.count_documents({"is_genossenschaft": True})
    unique = len(coll.distinct("content_fingerprint_xsrc",
                               {"is_genossenschaft": True,
                                "content_fingerprint_xsrc": {"$exists": True}}))
    by_bt = list(coll.aggregate([
        {"$match": {"is_genossenschaft": True}},
        {"$group": {"_id": {"bt": "$bautraeger", "src": "$coop_source"},
                    "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ]))
    stamp = datetime.date.today().isoformat()
    lines = [f"# Co-op coverage {stamp}",
             f"total co-op docs: {total}",
             f"unique deduped units (xsrc fp): {unique}", "", "by bautraeger/source:"]
    lines += [f"  {r['_id'].get('bt')} / {r['_id'].get('src')}: {r['n']}" for r in by_bt]
    report = "\n".join(lines)
    print(report)
    os.makedirs("Project/log", exist_ok=True)
    open(f"Project/log/coop_coverage_{stamp}.txt", "w").write(report)

if __name__ == "__main__":
    main()
