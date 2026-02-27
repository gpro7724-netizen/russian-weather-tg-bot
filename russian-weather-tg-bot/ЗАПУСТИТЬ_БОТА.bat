@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Запуск бота из папки: %CD%
echo Файл: bot.py
echo.
python bot.py
pause
