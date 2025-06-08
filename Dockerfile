# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if any (e.g., for certain Python packages)
# Example: if a package needed build-essential or libpq-dev
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     libpq-dev \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
# This assumes your source code is in a 'src' directory at the root of your project.
COPY ./src ./src
COPY ./data ./data # If sample data is needed by the app at runtime (e.g. sample_email.eml for CLI)

# Expose the port the app runs on (FastAPI default is 8000)
EXPOSE 8000

# Define environment variables (can be overridden in docker-compose.yml or at runtime)
# These are defaults; many should be overridden for security or functionality.

# MongoDB connection
ENV MONGO_URI="mongodb://mongo:27017/activity_db_default" # Points to the 'mongo' service in docker-compose
ENV AUTH_MONGO_DB_NAME="auth_db_default"

# JWT Authentication
ENV JWT_SECRET_KEY="default_dev_secret_key_for_docker_do_not_use_in_prod" # CRITICAL: Override in production
ENV ACCESS_TOKEN_EXPIRE_MINUTES="30"

# Microsoft Graph API Credentials (Leave blank, expect override)
ENV AZURE_CLIENT_ID=""
ENV AZURE_CLIENT_SECRET=""
ENV AZURE_TENANT_ID=""
ENV GRAPH_TARGET_USER_ID=""
ENV GRAPH_MAIL_FOLDER="Inbox"

# Python settings
ENV PYTHONUNBUFFERED=1 # Ensures print() statements are sent straight to terminal (Docker logs)
ENV PYTHONPATH="/app"  # Ensures src directory is in Python path for imports like src.api.main

# Command to run the application
# The src.api.main:app refers to the FastAPI instance 'app' in the file src/api/main.py
# Using --host 0.0.0.0 makes the app accessible from outside the container.
# --reload is good for development, should be removed for production images.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
