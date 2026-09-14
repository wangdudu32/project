#!/bin/bash

# Function to display help
show_help() {
    echo "Mini Qwen AutoQuestion System"
    echo "Usage: ./run.sh [OPTION]"
    echo ""
    echo "Options:"
    echo "  web             Start the Web Interface (Frontend + Backend) [Default]"
    echo "  cli <pdf_path>  Run in CLI mode to generate questions from a PDF"
    echo "  help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run.sh"
    echo "  ./run.sh cli /path/to/document.pdf"
}

# Check arguments
source /data/fx/wuli/anaconda3/etc/profile.d/conda.sh
conda activate auto_question

MODE=${1:-web}

if [ "$MODE" = "help" ]; then
    show_help
    exit 0
fi

if [ "$MODE" = "cli" ]; then
    PDF_PATH=$2
    if [ -z "$PDF_PATH" ]; then
        echo "Error: PDF path required for CLI mode."
        echo "Usage: ./run.sh cli <pdf_path>"
        exit 1
    fi
    
    echo "Starting CLI Mode..."
    export PYTHONPATH=$PYTHONPATH:$(pwd)/backend
    python3 cli_app.py "$PDF_PATH"
    exit 0
fi

echo "Starting Mini Qwen AutoQuestion System (Web Mode)..."

cleanup() {
    echo "Stopping processes..."
    if [ -n "$BACKEND_PID" ]; then kill $BACKEND_PID; fi
    if [ -n "$FRONTEND_PID" ]; then kill $FRONTEND_PID; fi
    exit
}

trap cleanup SIGINT

echo "=== Setting up Backend ==="
cd backend

if ! pip show fastapi &> /dev/null; then
    echo "Installing backend dependencies..."
    pip install -r requirements.txt
fi

echo "Starting Backend Server..."
export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "Backend started with PID $BACKEND_PID"

echo "=== Setting up Frontend ==="
cd ../frontend
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo "Starting Frontend Server..."
npm run dev -- --host &
FRONTEND_PID=$!
echo "Frontend started with PID $FRONTEND_PID"

echo "System is running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173" 

wait
