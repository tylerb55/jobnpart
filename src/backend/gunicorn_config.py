"""
Gunicorn configuration file for FastAPI application.
Handles long-running operations like building repair tree indexes.
"""

import multiprocessing
import os

# Worker timeout in seconds
# Set to 15 minutes to allow for index building (encoding large sets of descriptions)
timeout = 900

# Graceful timeout - time to wait for workers to finish before force killing
graceful_timeout = 30

# Number of worker processes
# For CPU-bound tasks (like model encoding), use fewer workers
# For Render's free tier, keep it low to avoid memory issues
workers = int(os.getenv("GUNICORN_WORKERS", "2"))

# Worker class - use uvicorn workers for async FastAPI
worker_class = "uvicorn.workers.UvicornWorker"

# Binding
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = os.getenv("LOG_LEVEL", "info")

# Keep alive for Render
keepalive = 120

# Maximum requests per worker before restart (helps with memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Preload app to save memory (shared code between workers)
# Note: Be careful with this if you have global state
preload_app = False

# Worker connections (only relevant for async workers)
worker_connections = 1000

print(f"""
╔══════════════════════════════════════════════════════════════╗
║                   Gunicorn Configuration                      ║
╠══════════════════════════════════════════════════════════════╣
║  Workers:              {workers:<40} ║
║  Worker Class:         {worker_class:<40} ║
║  Timeout:              {timeout}s (15 minutes)                        ║
║  Graceful Timeout:     {graceful_timeout}s                                   ║
║  Binding:              {bind:<40} ║
║  Log Level:            {loglevel:<40} ║
╚══════════════════════════════════════════════════════════════╝
""")

