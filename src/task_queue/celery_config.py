# src/task_queue/celery_config.py
import os

# --- Broker and Result Backend Configuration ---
# Default Redis URL if not set in environment.
# For local development with docker-compose, this would typically be 'redis://redis:6379/0'
# where 'redis' is the service name in docker-compose.yml.
# For local development without Docker, it might be 'redis://localhost:6379/0'.
# For cloud deployment, this would point to a managed Redis instance (e.g., Memorystore, Elasticache).
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

broker_url = REDIS_URL
result_backend = REDIS_URL # Using Redis as the result backend as well

# --- Serialization ---
# Using json for broader compatibility, but pickle is more feature-rich for Python objects.
# Consider security implications if using pickle with untrusted sources.
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json'] # Only accept json serialized content

# --- Timezone ---
# It's good practice to use UTC for internal operations.
timezone = 'UTC'
enable_utc = True # Ensures Celery uses UTC

# --- Task Routing and Discovery (Optional for now, but good to be aware of) ---
# Example: Define specific queues or import paths for task discovery.
# task_routes = {
#     'src.ingestion_context.tasks.process_ingested_email_task': {'queue': 'ingestion'},
#     'src.analysis_context.tasks.analyze_content_task': {'queue': 'analysis'},
# }
# imports = ('src.ingestion_context.tasks', 'src.analysis_context.tasks') # Helps worker discover tasks

# --- Optional: More Advanced Settings ---
# task_track_started = True  # If you want tasks to report 'STARTED' state.
# result_expires = 3600      # Results stored in backend expire after 1 hour (default is 1 day).
# broker_connection_retry_on_startup = True # Retry connection to broker on worker startup.

# --- Worker Concurrency (Example - can also be set via CLI) ---
# worker_concurrency = 4 # Number of child processes processing the queue. Default is number of CPUs.

# --- Logging (Example - can be configured more extensively) ---
# worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
# worker_task_log_format = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

# For Flower monitoring tool (if used later)
# address = '0.0.0.0' # Flower bind address
# port = 5555         # Flower port

print(f"Celery tasks will use Redis at: {REDIS_URL}")
