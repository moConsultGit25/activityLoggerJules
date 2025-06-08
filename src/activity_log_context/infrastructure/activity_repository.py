import pymongo
from pymongo.errors import ConnectionFailure, OperationFailure
import dataclasses
from typing import List, Optional, Tuple # Changed Type to Tuple for list_paginated
import os

from ..domain.activity_record import ActivityRecord

DEFAULT_MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DEFAULT_MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "activity_db_default")
DEFAULT_MONGO_COLLECTION_NAME = "activity_records"

class MongoActivityRepository:
    """
    A MongoDB repository for storing and retrieving ActivityRecord objects.
    """

    def __init__(self,
                 mongo_uri: str = DEFAULT_MONGO_URI,
                 db_name: str = DEFAULT_MONGO_DB_NAME,
                 collection_name: str = DEFAULT_MONGO_COLLECTION_NAME):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name

        try:
            self.client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            print(f"Successfully connected to MongoDB at {self.mongo_uri}, db '{self.db_name}', collection '{self.collection_name}'.")
        except ConnectionFailure as e:
            print(f"Error: Could not connect to MongoDB at {self.mongo_uri}. Details: {e}")
            self.client = None; self.db = None; self.collection = None
        except Exception as e:
            print(f"An unexpected error occurred during MongoDB init: {e}")
            self.client = None; self.db = None; self.collection = None

    def _ensure_connected(self) -> bool:
        if self.collection is None:
            print("Error: MongoDB collection is not available.")
            return False
        return True

    def _to_activity_record(self, document: dict) -> Optional[ActivityRecord]:
        """Converts a MongoDB document (dict) to an ActivityRecord, filtering unknown fields."""
        if document is None:
            return None
        document.pop('_id', None)
        valid_fields = {f.name for f in dataclasses.fields(ActivityRecord)}
        filtered_doc = {k: v for k, v in document.items() if k in valid_fields}
        try:
            return ActivityRecord(**filtered_doc)
        except TypeError as te:
            print(f"Warning: Skipping document due to TypeError (likely missing fields or type mismatch): {te}. Document: {document}")
            return None

    def add(self, activity_record: ActivityRecord) -> bool:
        if not self._ensure_connected(): return False
        try:
            record_dict = dataclasses.asdict(activity_record)
            insert_result = self.collection.insert_one(record_dict)
            print(f"ActivityRecord '{activity_record.record_id}' added with _id '{insert_result.inserted_id}'.")
            return True
        except OperationFailure as e:
            print(f"Error: MongoDB operation failed during add: {e}"); return False
        except Exception as e:
            print(f"Unexpected error during add: {e}"); return False

    def get_by_id(self, record_id: str) -> Optional[ActivityRecord]:
        if not self._ensure_connected(): return None
        try:
            document = self.collection.find_one({"record_id": record_id})
            return self._to_activity_record(document)
        except OperationFailure as e:
            print(f"Error: MongoDB operation failed during get_by_id: {e}"); return None
        except Exception as e:
            print(f"Unexpected error during get_by_id: {e}"); return None

    def list_paginated(self,
                       skip: int = 0,
                       limit: int = 100,
                       sort_by: str = 'logged_at',
                       sort_order: int = pymongo.DESCENDING  # Use pymongo constants
                      ) -> Tuple[List[ActivityRecord], int]:
        if not self._ensure_connected(): return ([], 0)

        records = []
        total_items = 0
        try:
            # Get total count (ignoring pagination for total)
            total_items = self.collection.count_documents({}) # Or apply filters if any are added later

            cursor = self.collection.find({}).sort(sort_by, sort_order).skip(skip).limit(limit)
            for doc in cursor:
                record = self._to_activity_record(doc)
                if record:
                    records.append(record)
            return records, total_items
        except OperationFailure as e:
            print(f"Error: MongoDB operation failed during list_paginated: {e}")
            return ([], total_items) # Return empty list but potentially correct count if count_documents succeeded
        except Exception as e:
            print(f"Unexpected error during list_paginated: {e}")
            return ([], 0)

    def list_all(self, limit: int = 100) -> List[ActivityRecord]:
        """Retrieves ActivityRecords, effectively the first page of list_paginated."""
        # Refactored to use list_paginated
        records, _ = self.list_paginated(skip=0, limit=limit)
        return records

if __name__ == '__main__':
    print("\n--- MongoDB ActivityRepository Demonstration (with Pagination) ---")
    repo = MongoActivityRepository()

    if repo.collection is not None:
        print("\n1. Adding some sample records for pagination test...")
        for i in range(5): # Add 5 records
            repo.add(ActivityRecord(
                subject=f"Paginated Record {i+1}",
                ingested_at=f"2023-01-01T10:0{i}:00Z",
                logged_at=f"2023-01-01T10:0{i}:05Z", # Ensure logged_at varies for sorting
                source_channel="pagination_test", source_identifier=f"pg_test_{i}"
            ))

        print("\n2. Testing list_paginated():")
        # Page 1, 2 items per page, sort by logged_at descending (default)
        records_page1, total_count1 = repo.list_paginated(skip=0, limit=2)
        print(f"Page 1 (2 items): Found {len(records_page1)} records. Total items in DB: {total_count1}")
        for r in records_page1: print(f"  - {r.subject} (Logged: {r.logged_at})")

        # Page 2, 2 items per page
        records_page2, total_count2 = repo.list_paginated(skip=2, limit=2)
        print(f"Page 2 (2 items): Found {len(records_page2)} records. Total items in DB: {total_count2}")
        for r in records_page2: print(f"  - {r.subject} (Logged: {r.logged_at})")

        # Page 1, 2 items, sort by subject ascending
        records_sorted_asc, total_count_sorted = repo.list_paginated(skip=0, limit=3, sort_by='subject', sort_order=pymongo.ASCENDING)
        print(f"Page 1 (3 items, sorted by subject ASC): Found {len(records_sorted_asc)} records. Total: {total_count_sorted}")
        for r in records_sorted_asc: print(f"  - {r.subject} (Logged: {r.logged_at})")

        print("\n3. Testing refactored list_all() (should get first 3 of the 5):")
        all_limited_records = repo.list_all(limit=3)
        print(f"list_all(limit=3): Found {len(all_limited_records)} records.")
        # They should be sorted by logged_at descending by default from list_paginated
        for r in all_limited_records: print(f"  - {r.subject} (Logged: {r.logged_at})")

        # Basic get_by_id still works (assuming one of the paginated records)
        if records_page1:
             retrieved = repo.get_by_id(records_page1[0].record_id)
             print(f"\nRetrieved by ID '{records_page1[0].record_id}': Subject '{retrieved.subject if retrieved else 'Not Found'}'")
    else:
        print("\nSkipping repository operations as MongoDB connection failed.")
    print("\n--- End of Demonstration ---")
