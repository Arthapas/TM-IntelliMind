#!/bin/bash

# TM IntelliMind Development Server Startup Script
# This script ensures the development server starts with proper configuration

# Load port from .env.development or use default
if [ -f ".env.development" ]; then
    export $(grep -E '^DJANGO_PORT=' .env.development | xargs)
fi
PORT=${DJANGO_PORT:-8006}

# Function to check if port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        return 1
    else
        return 0
    fi
}

# Find available port starting from configured port
ORIGINAL_PORT=$PORT
while ! check_port $PORT; do
    echo "Port $PORT is already in use."
    PORT=$((PORT + 1))
done

if [ $PORT -ne $ORIGINAL_PORT ]; then
    echo "Using alternative port: $PORT"
fi

# Check if LMStudio is running (optional)
if ! curl -s http://localhost:1234/v1/models > /dev/null 2>&1; then
    echo "Warning: LMStudio is not running at http://localhost:1234"
    echo "Insight generation will not work without LMStudio."
    echo "Start LMStudio or update LLM_API_BASE in .env.development"
    echo ""
fi

# Ensure we're using the development environment
if [ ! -f ".env.development" ]; then
    echo "Warning: .env.development not found. Server may not start properly."
    echo "Run: cp .env.example .env.development"
    echo ""
fi

# Start the Django development server
echo "Starting TM IntelliMind development server on http://127.0.0.1:$PORT/"
echo "Press Ctrl+C to stop the server"
echo ""

# Run the server
python3 manage.py runserver $PORT