import pymongo
import os
import json

# Load config
config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
if not os.path.exists(config_path):
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')

with open(config_path) as f:
    config = json.load(f)

MONGO_URI = config.get('mongodb_uri', 'mongodb://localhost:27017/')
DB_NAME = 'immo'
COLLECTION_NAME = 'listings'

client = pymongo.MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COLLECTION_NAME]

# Fix bezirk
for doc in col.find({"bezirk": {"$type": "object"}}):
    bezirk = doc['bezirk']
    new_bezirk = str(bezirk) if bezirk is not None else None
    col.update_one({'_id': doc['_id']}, {'$set': {'bezirk': new_bezirk}})
    print(f"Fixed bezirk for _id={doc['_id']}")

# Fix source
for doc in col.find({"source": {"$type": "object"}}):
    source = doc['source']
    new_source = str(source) if source is not None else None
    col.update_one({'_id': doc['_id']}, {'$set': {'source': new_source}})
    print(f"Fixed source for _id={doc['_id']}")

print("Done fixing bezirk and source fields.") 