import logging
import sys

# Configure root logger before importing app
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Add filter to remove gunicorn "Handling signal: winch" messages
class GunicornFilter(logging.Filter):
    def filter(self, record):
        # Filter out gunicorn signal handling messages
        if 'Handling signal: winch' in record.getMessage():
            return False
        return True

# Create console handler and set level
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.addFilter(GunicornFilter())

# Create formatter and add to handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add handlers to the root logger
root_logger.addHandler(console_handler)

# Now import app after configuring the root logger
from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)