import pymongo
from pymongo.errors import ConnectionFailure, OperationFailure
import dataclasses
from typing import List, Optional, Type # Added Type for factory method
import os # For environment variables

# Adjust import path to access ActivityRecord from the domain layer of the same context
from ..domain.activity_record import ActivityRecord

# Default MongoDB connection parameters (can be overridden by environment variables)
DEFAULT_MONGO_URI = "mongodb://localhost:27017/"
DEFAULT_MONGO_DB_NAME = "activity_db_default"
DEFAULT_MONGO_COLLECTION_NAME = "activity_records"

class MongoActivityRepository:
    """
    A MongoDB repository for storing and retrieving ActivityRecord objects.
    """

    def __init__(self,
                 mongo_uri: str = os.environ.get("MONGO_URI", DEFAULT_MONGO_URI),
                 db_name: str = os.environ.get("MONGO_DB_NAME", DEFAULT_MONGO_DB_NAME),
                 collection_name: str = DEFAULT_MONGO_COLLECTION_NAME):
        """
        Initializes the repository with a MongoDB client, database, and collection.

        Args:
            mongo_uri (str): The MongoDB connection string.
            db_name (str): The name of the database to use.
            collection_name (str): The name of the collection to use.
        """
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name

        try:
            self.client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            print(f"Successfully connected to MongoDB at {self.mongo_uri}, database '{self.db_name}', collection '{self.collection_name}'.")
        except ConnectionFailure as e:
            print(f"Error: Could not connect to MongoDB at {self.mongo_uri}. Is the server running? Details: {e}")
            self.client = None
            self.db = None
            self.collection = None
        except Exception as e:
            print(f"An unexpected error occurred during MongoDB initialization: {e}")
            self.client = None
            self.db = None
            self.collection = None


    def _ensure_connected(self) -> bool:
        if self.collection is None:
            print("Error: MongoDB collection is not available. Please check connection.")
            return False
        return True

    def add(self, activity_record: ActivityRecord) -> bool:
        """
        Adds an ActivityRecord to the MongoDB collection.

        Args:
            activity_record (ActivityRecord): The activity record to add.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not self._ensure_connected():
            return False

        try:
            record_dict = dataclasses.asdict(activity_record)
            # MongoDB uses _id as the primary key. If record_id is meant to be it, ensure it's set as _id or indexed.
            # If record_id is distinct from _id, that's fine too.
            # For simplicity, we'll let MongoDB generate its own _id.
            # If you want to use activity_record.record_id as MongoDB's _id, you can do:
            # record_dict['_id'] = activity_record.record_id

            insert_result = self.collection.insert_one(record_dict)
            print(f"ActivityRecord with record_id '{activity_record.record_id}' added to MongoDB with _id '{insert_result.inserted_id}'.")
            return True
        except OperationFailure as e:
            print(f"Error: MongoDB operation failed during add: {e}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred during add: {e}")
            return False

    def get_by_id(self, record_id: str) -> Optional[ActivityRecord]:
        """
        Retrieves an ActivityRecord from MongoDB by its record_id.

        Args:
            record_id (str): The ID of the record to retrieve.

        Returns:
            Optional[ActivityRecord]: The ActivityRecord instance if found, else None.
        """
        if not self._ensure_connected():
            return None

        try:
            # Assuming 'record_id' is a field in your MongoDB documents, not the MongoDB '_id'.
            document = self.collection.find_one({"record_id": record_id})
            if document:
                # Remove MongoDB's _id before converting to dataclass if it's not part of ActivityRecord
                document.pop('_id', None)
                # Need to handle potential extra fields in document not in ActivityRecord or missing fields
                # For simplicity, this assumes direct mapping. A more robust solution would filter keys.

                # Filter dict to only include fields defined in ActivityRecord
                valid_fields = {f.name for f in dataclasses.fields(ActivityRecord)}
                filtered_doc = {k: v for k, v in document.items() if k in valid_fields}

                return ActivityRecord(**filtered_doc)
            return None
        except OperationFailure as e:
            print(f"Error: MongoDB operation failed during get_by_id: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during get_by_id: {e}")
            return None


    def list_all(self, limit: int = 100) -> List[ActivityRecord]:
        """
        Retrieves all ActivityRecords from MongoDB, up to a specified limit.

        Args:
            limit (int): The maximum number of records to retrieve.

        Returns:
            List[ActivityRecord]: A list of ActivityRecord instances.
        """
        if not self._ensure_connected():
            return []

        records = []
        try:
            documents = self.collection.find().limit(limit)
            for doc in documents:
                doc.pop('_id', None)
                valid_fields = {f.name for f in dataclasses.fields(ActivityRecord)}
                filtered_doc = {k: v for k, v in doc.items() if k in valid_fields}
                try:
                    records.append(ActivityRecord(**filtered_doc))
                except TypeError as te: # Handles cases where a field might be missing in doc but required by dataclass
                    print(f"Warning: Skipping document due to TypeError (likely missing fields or type mismatch): {te}. Document: {doc}")

            return records
        except OperationFailure as e:
            print(f"Error: MongoDB operation failed during list_all: {e}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred during list_all: {e}")
            return []

# Step 5: Basic example usage or test snippet
if __name__ == '__main__':
    print("\n--- MongoDB ActivityRepository Demonstration ---")

    # This example assumes a local MongoDB server is running.
    # If not, it will print connection error messages from the constructor.
    repo = MongoActivityRepository() # Uses defaults: mongodb://localhost:27017/, db: activity_db_default

    if repo.collection is not None: # Proceed only if connection seemed successful
        print("\n1. Creating and Adding a sample ActivityRecord:")
        sample_record = ActivityRecord(
            # record_id is auto-generated by default factory in ActivityRecord
            ingested_at="2023-01-01T10:00:00Z",
            source_channel="email_test",
            source_identifier="test_email_123.eml",
            sender="test_sender@example.com",
            recipient="test_recipient@example.com",
            subject="Mongo Demo Subject",
            summary="This is a test summary for MongoDB.",
            disposition="Test Category",
            full_content_reference="/path/to/test_email_123.eml",
            # logged_at is auto-generated
            metadata={"custom_key": "custom_value", "processed_by_version": "1.0"}
        )

        # Use a unique record_id for testing get_by_id
        test_record_id = sample_record.record_id

        add_success = repo.add(sample_record)
        print(f"Add operation successful: {add_success}")

        if add_success:
            print(f"\n2. Retrieving the record by ID ('{test_record_id}'):")
            retrieved_record = repo.get_by_id(test_record_id)
            if retrieved_record:
                print(f"Retrieved: {retrieved_record.subject}, Disposition: {retrieved_record.disposition}")
                assert retrieved_record.record_id == test_record_id
                assert retrieved_record.subject == "Mongo Demo Subject"
            else:
                print(f"Record with ID '{test_record_id}' not found after add. This might indicate an issue with add/get logic or data consistency.")

        print("\n3. Listing all records (limit 10):")
        all_records = repo.list_all(limit=10)
        if all_records:
            print(f"Found {len(all_records)} records:")
            for rec in all_records:
                print(f"  - ID: {rec.record_id}, Subject: {rec.subject}, Logged: {rec.logged_at}")
        else:
            print("No records found or error during list_all.")

        # Clean up: Optional - delete the test record
        # For simplicity, not deleting here, but in real tests, you would.
        # Example: repo.collection.delete_one({"record_id": test_record_id})
        # print(f"\nNote: Test record with ID '{test_record_id}' was not deleted from the database.")

    else:
        print("\nSkipping repository operations demonstration as MongoDB connection failed during initialization.")
        print("Please ensure a MongoDB server is running on mongodb://localhost:27017/ if you wish to run this demo.")

    print("\n--- End of Demonstration ---")
