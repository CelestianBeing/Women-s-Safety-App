"""gunicorn.conf.py — production server configuration."""
import multiprocessing

# Bind
bind = "0.0.0.0:5000"

# Workers: 2-4 × CPU cores
workers    = min(4, multiprocessing.cpu_count() * 2 + 1)
worker_class = "sync"
threads    = 2
timeout    = 120           # route computation can take ~30s on first run

# Graceful shutdown
graceful_timeout = 30
keepalive        = 5

# Logging
loglevel    = "info"
accesslog   = "logs/access.log"
errorlog    = "logs/error.log"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)s'

# Reload on code changes (dev only — remove in production)
# reload = True
