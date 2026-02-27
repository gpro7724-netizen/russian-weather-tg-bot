@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Останавливаю ВСЕ процессы Python...
echo ========================================
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo Запуск бота (местное время, не UTC): %CD%
echo Если в Telegram по-прежнему UTC - бот крутится на сервере, не здесь.
echo.
python bot.py
if errorlevel 1 pause
