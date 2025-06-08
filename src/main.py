import argparse
import os # For file existence check and other OS interactions if needed

# Import application services and context-specific setup
from src.ingestion_context.application import IngestionService

# Import event handler registration functions
from src.analysis_context.interfaces.event_handlers import register_analysis_event_handlers
from src.activity_log_context.interfaces.event_handlers import register_activity_log_event_handlers
# The global dispatcher is implicitly used by these registration functions and services when they publish.
# from src.shared_kernel.events import dispatcher # Not strictly needed here unless interacting directly

def setup_application():
    """
    Initializes the application by registering event handlers.
    This ensures that when events are published, the appropriate handlers
    across different contexts are notified.
    """
    print("Starting application setup...")

    # Register event handlers from all relevant contexts
    register_analysis_event_handlers()
    register_activity_log_event_handlers()

    print("Application setup complete: Event handlers registered.")
    print("----------------------------------------------------")

def main():
    """
    Main function to run the email processing pipeline.
    Parses command-line arguments, sets up the application,
    and starts the ingestion process.
    """
    parser = argparse.ArgumentParser(description="Process a single email file and trigger event-driven workflow.")
    parser.add_argument(
        "--email-file",
        type=str,
        required=True,
        help="Path to the .eml file to process."
    )
    # Future arguments could include config paths, specific context flags, etc.
    # parser.add_argument("--config", type=str, help="Path to a configuration file.")

    args = parser.parse_args()

    # --- Application Setup ---
    setup_application()

    # --- Process Email ---
    print(f"Processing email file: {args.email_file}")

    if not os.path.isfile(args.email_file):
        print(f"Error: Email file not found at '{args.email_file}'. Please provide a valid file path.")
        return

    # Initialize the primary service that starts the process
    ingestion_service = IngestionService()

    # Start the process by ingesting the email.
    # This will trigger an EmailIngestedEvent, which then triggers analysis,
    # which in turn triggers ContentAnalyzedEvent, leading to logging.
    raw_email_obj = ingestion_service.ingest_email_from_file(args.email_file)

    if raw_email_obj:
        print(f"\nEmail file '{args.email_file}' ingested successfully.")
        print(f"  -> RawEmail ID: {raw_email_obj.message_id}")
        print(f"  -> This should have triggered analysis and logging via domain events.")
        print(f"  -> Check console output from handlers and MongoDB (if running) for 'activity_records' in your database (e.g., 'activity_db_default').")
    else:
        print(f"\nFailed to ingest email file '{args.email_file}'. See previous error messages for details.")

    print("----------------------------------------------------")
    print("Processing finished.")

if __name__ == '__main__':
    # This is the main entry point of the application when run as a script.
    main()
