# Gunicorn configuration file for Genesis Trading Platform
import logging

# Logging configuration
loggers = {
    # Disable gunicorn logging of winch signals
    'gunicorn.error': {
        'level': 'WARNING',
        'handlers': ['console'],
        'propagate': False,
    },
    'gunicorn.access': {
        'level': 'INFO',
        'handlers': ['console'],
        'propagate': False,
    },
}

# Bind to all interfaces
bind = '0.0.0.0:5000'

# Worker settings
workers = 1
worker_class = 'sync'

# Reload on code changes
reload = True

# Use reuse_port for better restarts
reuse_port = True

# Configure logging
accesslog = '-'  # stdout
errorlog = '-'   # stderr
loglevel = 'warning'  # Only show warnings and above for gunicorn itself

# Add timestamp to logs
access_log_format = '%({X-Real-IP}i)s %(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
