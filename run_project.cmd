@echo off
cd /d "%~dp0"
curl.exe --silent --fail --max-time 2 --output NUL http://127.0.0.1:5000/api/chat/status
if not errorlevel 1 (
  start "" "http://127.0.0.1:5000"
  exit /b 0
)
set "PYTHONDONTWRITEBYTECODE=1"
set "CHATBOT_BACKEND=llama_cpp"
set "CHATBOT_GGUF_PATH=%~dp0models\xanhnon-style-v2-f16.gguf"
set "CHATBOT_MAX_NEW_TOKENS=256"
"%~dp0.venv\Scripts\python.exe" -B app.py
pause
