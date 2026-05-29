#!/bin/bash
cd "$(dirname "$0")/.."
pip install -r requirements.txt -q
echo "✅ Starting FaMTNarriAI API v2.0"
echo "   Docs: http://localhost:8000/docs"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
