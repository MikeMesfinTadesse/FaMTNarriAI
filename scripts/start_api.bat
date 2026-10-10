@echo off
title FaMTNarriAI API Server
color 0D
echo.
echo  ==========================================
echo   FaMTNarriAI REST API v2.0
echo  ==========================================
echo.
cd /d "%~dp0.."
pip install -r requirements.txt -q
echo  [OK] Dependencies ready
echo.
echo  Starting API server...
echo  Interactive docs: http://localhost:8000/docs
echo  Health check:     http://localhost:8000/api/v2/health
echo.
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
pause
