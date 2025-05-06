#!/bin/bash

# Use custom gunicorn config to reduce log noise
gunicorn --config gunicorn_config.py --bind 0.0.0.0:5000 --reuse-port --reload main:app
