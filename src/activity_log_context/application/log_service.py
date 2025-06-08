# src/activity_log_context/application/log_service.py

from ..domain.activity_record import ActivityRecord
from ..infrastructure import MongoActivityRepository
from src.shared_kernel.events import ContentAnalyzedEvent

import datetime
import uuid
import math # For ceiling division for total_pages
import dataclasses # For asdict
import pymongo # For sort order constants

from typing import TYPE_CHECKING, Dict, List, Any
if TYPE_CHECKING:
    from src.ingestion_context.domain.raw_email import RawEmail
    from src.analysis_context.domain.analyzed_content import AnalyzedContent

class LogService:
    def __init__(self, activity_log_repo: MongoActivityRepository | None = None):
        if activity_log_repo:
            self.activity_log_repo = activity_log_repo
        else:
            self.activity_log_repo = MongoActivityRepository()

        if self.activity_log_repo.collection is None:
            print("LogService WARN: MongoActivityRepository failed to connect. Logging/retrieval will not work.")
        else:
            print("LogService initialized with MongoActivityRepository.")

    def record_activity_from_event_data(self, event: ContentAnalyzedEvent) -> ActivityRecord | None:
        print(f"LogService: Received ContentAnalyzedEvent for raw_email_id: {event.raw_email_id}")
        try:
            activity = ActivityRecord(
                ingested_at=event.received_at,
                source_channel="email",
                source_identifier=event.source_identifier,
                sender=event.sender,
                recipient=event.recipient,
                subject=event.subject,
                summary=event.summary,
                disposition=event.disposition,
                full_content_reference=f"raw_email_id:{event.raw_email_id}",
                metadata={
                    "analyzed_at": event.analyzed_at,
                    "keywords_found": event.keywords_found,
                    "original_body_snippet": event.body[:200] if event.body else ""
                }
            )
            save_success = self.activity_log_repo.add(activity)
            if save_success:
                print(f"LogService: Saved ActivityRecord ID {activity.record_id} for {event.raw_email_id}")
                return activity
            else:
                print(f"LogService: Failed to save ActivityRecord for {event.raw_email_id}")
                return None
        except Exception as e:
            print(f"LogService: Error creating/saving ActivityRecord from event: {e}")
            return None

    def get_activity_logs_paginated(
        self,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = 'logged_at',
        sort_order_str: str = 'desc' # Changed to string 'asc'/'desc' for API friendliness
    ) -> Dict[str, Any]:
        """
        Retrieves activity logs with pagination and sorting.
        Formats the output for API responses, including pagination metadata.
        """
        print(f"LogService: Getting activity logs - Page: {page}, Size: {page_size}, SortBy: {sort_by}, Order: {sort_order_str}")

        if page < 1: page = 1
        if page_size < 1: page_size = 10
        if page_size > 100: page_size = 100 # Max page size cap

        skip = (page - 1) * page_size

        mongo_sort_order = pymongo.DESCENDING if sort_order_str.lower() == 'desc' else pymongo.ASCENDING

        records, total_items = self.activity_log_repo.list_paginated(
            skip=skip,
            limit=page_size,
            sort_by=sort_by,
            sort_order=mongo_sort_order
        )

        # Convert ActivityRecord objects to dictionaries for the API response
        records_as_dicts = [dataclasses.asdict(record) for record in records]

        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0
        if total_pages == 0 and total_items > 0: # Ensure at least one page if items exist
             total_pages = 1


        return {
            "data": records_as_dicts,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }

    # Kept for potential direct use, though event-driven is primary
    def create_log_from_processed_data(
        self, raw_email: 'RawEmail', analyzed_content: 'AnalyzedContent', source_channel: str = "email"
    ) -> ActivityRecord | None:
        # (Implementation as before, calls self.activity_log_repo.add)
        print(f"LogService: Creating activity log directly for email ID: {raw_email.message_id}")
        activity_record = ActivityRecord.from_analysis(
            raw_email=raw_email, analyzed_content=analyzed_content, source_channel=source_channel
        )
        save_success = self.activity_log_repo.add(activity_record)
        return activity_record if save_success else None


if __name__ == '__main__':
    print("\n--- LogService Paginated Get Demonstration ---")
    log_service_instance = LogService() # Attempts to connect to MongoDB

    if log_service_instance.activity_log_repo.collection is not None:
        # Ensure some data exists (e.g., run the MongoActivityRepository's __main__ block first,
        # or add some records here if confident in the 'add' method via service)
        print("Attempting to add a few sample records for get_activity_logs_paginated test...")
        for i in range(3): # Add a few records to ensure some data
            evt_data = ContentAnalyzedEvent(
                raw_email_id=f"pag_test_{i}", sender=f"s{i}@e.com", recipient=f"r{i}@e.com",
                subject=f"LogService Pag Test {i}", body=f"Body {i}", received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_identifier=f"file{i}.eml", summary=f"Summary {i}", disposition=f"Disp {i}",
                analyzed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
            # Small delay to ensure logged_at might differ if that's the default sort key
            import time; time.sleep(0.01)
            log_service_instance.record_activity_from_event_data(evt_data)

        print("\nFetching page 1, size 2, sort by 'logged_at' descending:")
        paginated_result = log_service_instance.get_activity_logs_paginated(page=1, page_size=2, sort_by='logged_at', sort_order_str='desc')

        print(f"Response: Total Items: {paginated_result['total_items']}, Total Pages: {paginated_result['total_pages']}")
        print("Data:")
        for item in paginated_result['data']:
            print(f"  - ID: {item['record_id']}, Subject: {item['subject']}, Logged: {item['logged_at']}")

        print("\nFetching page 2, size 2, sort by 'subject' ascending:")
        paginated_result_subj_asc = log_service_instance.get_activity_logs_paginated(page=1, page_size=2, sort_by='subject', sort_order_str='asc')
        print(f"Response: Total Items: {paginated_result_subj_asc['total_items']}, Total Pages: {paginated_result_subj_asc['total_pages']}")
        print("Data:")
        for item in paginated_result_subj_asc['data']:
            print(f"  - ID: {item['record_id']}, Subject: {item['subject']}, Logged: {item['logged_at']}")
    else:
        print("\nSkipping LogService get operations as MongoDB connection failed.")

    print("\n--- End of LogService Paginated Get Demonstration ---")
