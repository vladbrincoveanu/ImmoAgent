import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import MagicMock
from Integration.mongodb_handler import MongoDBHandler


def _handler_with_fake_meta():
    h = MongoDBHandler.__new__(MongoDBHandler)   # bypass __init__ (no DB)
    h.client = MagicMock()
    h.db = MagicMock()
    h.source_meta_collection = MagicMock()
    return h


class TestSourceMeta(unittest.TestCase):
    def test_get_returns_empty_when_absent(self):
        h = _handler_with_fake_meta()
        h.source_meta_collection.find_one.return_value = None
        self.assertEqual(h.get_source_meta("ÖVW"), {})

    def test_get_strips_mongo_internals(self):
        h = _handler_with_fake_meta()
        h.source_meta_collection.find_one.return_value = {
            "_id": 1, "source": "ÖVW", "etag": "abc",
            "last_modified": "Mon", "page_hash": "h1"}
        self.assertEqual(h.get_source_meta("ÖVW"),
                         {"etag": "abc", "last_modified": "Mon", "page_hash": "h1"})

    def test_set_upserts_by_source(self):
        h = _handler_with_fake_meta()
        h.set_source_meta("ÖVW", etag="abc", last_modified="Mon", page_hash="h1")
        args, kwargs = h.source_meta_collection.update_one.call_args
        self.assertEqual(args[0], {"source": "ÖVW"})
        self.assertEqual(args[1]["$set"],
                         {"etag": "abc", "last_modified": "Mon", "page_hash": "h1"})
        self.assertTrue(kwargs.get("upsert"))


if __name__ == '__main__':
    unittest.main()
