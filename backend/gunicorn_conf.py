"""
Gunicorn Production Server Configuration for Apex CRM
Run via: gunicorn -c backend/gunicorn_conf.py backend.app:app
"""

import multiprocessing
import os

# Server Socket
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker Processes & Concurrency
# Recommended formula: (2 x $num_cores) + 1
cores = multiprocessing.cpu_count()
workers = int(os.getenv("WEB_CONCURRENCY", (2 * cores) + 1))
worker_class = "gthread"
threads = int(os.getenv("PYTHON_MAX_THREADS", 4))
worker_connections = 1000

# Lifecycle & Timeouts
timeout = int(os.getenv("WEB_TIMEOUT", 120))
keepalive = int(os.getenv("WEB_KEEPALIVE", 5))
max_requests = 1000
max_requests_jitter = 50
graceful_timeout = 30

# Logging
accesslog = os.getenv("ACCESS_LOG", "-")
errorlog = os.getenv("ERROR_LOG", "-")
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# Process Naming
proc_name = "apex_crm_app"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
