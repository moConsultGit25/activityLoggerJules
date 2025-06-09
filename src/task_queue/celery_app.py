# src/task_queue/celery_app.py
from celery import Celery

# Create the Celery application instance.
# The first argument is conventionally the name of the current module,
# but can be any unique name. Using a descriptive name like 'proj_task_queue'.
app = Celery('proj_task_queue')

# Load configuration from celery_config.py.
# Celery will look for uppercase settings in the specified object that match its own config keys
# (e.g., BROKER_URL, RESULT_BACKEND) or directly load attributes like `broker_url`.
app.config_from_object('src.task_queue.celery_config')

# --- Task Auto-Discovery ---
# Celery can automatically discover tasks in modules listed in the 'imports'
# configuration variable (in celery_config.py) or by using app.autodiscover_tasks().
# For autodiscover_tasks to work effectively with a custom project structure,
# it usually expects tasks to be defined in 'tasks.py' files within 'installed apps'
# (similar to a Django project).
#
# A common pattern for non-Django projects is to:
# 1. Define tasks in various modules (e.g., src.ingestion_context.tasks, src.analysis_context.tasks).
# 2. Ensure these modules import the `app` instance from this file (`from src.task_queue.celery_app import app`)
#    and use the `@app.task` decorator.
# 3. Add the paths to these task modules to an `imports` tuple in `celery_config.py`, e.g.:
#    `imports = ('src.ingestion_context.tasks', 'src.analysis_context.tasks')`
#    The Celery worker will then import these modules on startup, registering the tasks.
#
# Alternatively, if `app.autodiscover_tasks()` is used, you might need to structure your project
# such that it can find them, or provide a list of packages to scan.
# e.g., app.autodiscover_tasks(lambda: ['src.ingestion_context', 'src.analysis_context'])
# This tells Celery to look for 'tasks.py' inside these packages.
#
# For now, we will rely on explicit imports in `celery_config.py` or ensure task modules
# are imported somewhere during application initialization if not using the `imports` config.
# The `include` setting in Celery configuration is also a modern way to list task modules.
# Example (in celery_config.py):
# include=['src.ingestion_context.tasks', 'src.analysis_context.tasks']

# Explicitly list modules containing tasks for discovery by the worker.
# This is often more reliable than relying on autodiscover_tasks in complex project structures.
# Alternatively, this can be set in celery_config.py using the `imports` or `include` setting.
app.conf.update(
    imports=(
        'src.ingestion_context.tasks',
        # Add other task modules here as they are created, e.g.:
        # 'src.analysis_context.tasks',
        # 'src.activity_log_context.tasks',
    ),
    # Using 'include' is also common and sometimes preferred over 'imports'
    # include=[
    #     'src.ingestion_context.tasks',
    # ]
)


if __name__ == '__main__':
    # This block allows running the Celery worker directly using:
    # python -m src.task_queue.celery_app worker -l info
    #
    # However, the more common way to start a worker is via the Celery CLI:
    # celery -A src.task_queue.celery_app worker -l info -P eventlet (for Windows or if preferred)
    # celery -A src.task_queue.celery_app flower (to start Flower monitoring tool)
    #
    # The `app.start()` method with `argv` is typically used for embedding workers/beaters.
    # For CLI usage, `celery -A ...` is standard.
    # To make `python -m src.task_queue.celery_app worker ...` work as expected,
    # one might need to adjust sys.argv or use Celery's command-line program.
    # For simplicity, we'll rely on the `celery -A ...` command.
    # The following lines are more for programmatic start, not typical CLI worker start.
    # import sys
    # app.worker_main(sys.argv) # This is closer to what `celery worker` does
    print("Celery app instance created. To start a worker, use the Celery CLI:")
    print("Example: celery -A src.task_queue.celery_app worker -l info")
    print("Or, if you have specific task modules, ensure they are in 'imports' or 'include' in celery_config.py")
