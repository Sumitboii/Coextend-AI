@echo off
title Coextend PI Server
echo Starting on http://localhost:8000
cd /d "C:\Users\ssing\OneDrive\Desktop\Project Files\Coextend AI\prospect-intelligence"
call .venv\Scripts\activate.bat
python -m uvicorn main:app --reload
pause
