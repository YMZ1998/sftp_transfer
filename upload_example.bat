@echo off
setlocal
cd /d "%~dp0"

REM Edit these values before running.
set HOST=192.168.1.200
set USERNAME=oct
set LOCAL=D:\Data\OCT
set REMOTE=/data/OCT

python run.py upload ^
  --host %HOST% ^
  --username %USERNAME% ^
  --local "%LOCAL%" ^
  --remote "%REMOTE%"

pause
