"""
Gunicorn Configuration File

Production-grade configuration for the Reactor Stabilizer application.
"""

import os
import multiprocessing

bind = f"0.0.0.0:{os.environ.get('PORT', '3000')}"
backlog = 2048

workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

accesslog = 'logs/gunicorn_access.log'
errorlog = 'logs/gunicorn_error.log'
loglevel = os.environ.get('LOG_LEVEL', 'info').lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

proc_name = 'reactor-stabilizer'

daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

keyfile = None
certfile = None

limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190