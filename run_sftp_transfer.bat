@echo off
setlocal
cd /d "%~dp0"
python run.py %*
exit /b %ERRORLEVEL%
