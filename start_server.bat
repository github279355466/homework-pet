@echo off
cd /d C:\homework-pet\app
call C:\homework-pet\venv\Scripts\activate.bat
python -m uvicorn main:app --host 127.0.0.1 --port 5000 --workers 2
pause
