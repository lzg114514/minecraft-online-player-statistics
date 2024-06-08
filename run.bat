@echo off
:loop
python main.py
timeout /t 3 >nul
goto loop