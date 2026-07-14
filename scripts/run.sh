#!/bin/bash

# Change directory to the workspace root
cd "/mnt/bridge/dev/personal/j*b"

# 1. Wait for startup and network connection
echo "Sleeping for 2 minutes to allow startup and network connection..."
sleep 120

# 2. Run the recruiting platform pipeline
echo "Running recruiting platform pipeline..."
.venv/bin/recruiting-platform run
