@echo off
set "PYTHONPATH=%~dp0src"
python "%~dp0run_app.py"
if errorlevel 1 pause

