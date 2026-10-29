@echo off
chcp 65001 >nul
title Karbordi - Local File Transfer
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py
) else (
  python server.py
)
if errorlevel 1 (
  echo.
  echo برنامه اجرا نشد. مطمئن شوید Python 3 نصب شده است.
  echo راهنما: https://www.python.org/downloads/windows/
  pause
)
