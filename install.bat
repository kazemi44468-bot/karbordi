@echo off
chcp 65001 >nul
setlocal
title نصب کاربُردی
cd /d "%~dp0"

echo ==========================================
echo   نصب میان‌بر دسکتاپ کاربُردی
echo ==========================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python روی این رایانه پیدا نشد.
    echo ابتدا Python 3.10 یا جدیدتر را از این نشانی نصب کنید:
    echo https://www.python.org/downloads/windows/
    echo هنگام نصب گزینه Add Python to PATH را فعال کنید.
    echo.
    pause
    exit /b 1
  )
)

set "TARGET=%~dp0start.bat"
set "SHORTCUT=%USERPROFILE%\Desktop\کاربُردی - انتقال فایل.lnk"
set "ICON=%SystemRoot%\System32\shell32.dll,146"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut($env:USERPROFILE + '\Desktop\کاربُردی - انتقال فایل.lnk'); $s.TargetPath=$env:ComSpec; $s.Arguments='/c ""%~dp0start.bat""'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,146'; $s.Description='اجرای برنامه انتقال فایل کاربُردی'; $s.Save()"

if errorlevel 1 (
  echo ساخت میان‌بر ناموفق بود.
  pause
  exit /b 1
)

echo میان‌بر روی دسکتاپ ساخته شد:
echo کاربُردی - انتقال فایل
echo.
echo از این پس برای اجرا روی همان میان‌بر دوبار کلیک کنید.
echo پنجره برنامه را تا پایان انتقال فایل باز نگه دارید.
echo.
pause
