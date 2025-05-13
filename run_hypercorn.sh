#!/bin/bash
hypercorn --bind 0.0.0.0:5000 --reload main:app
