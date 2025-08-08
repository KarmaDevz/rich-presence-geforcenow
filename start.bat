@echo off
echo Iniciando Rich Presence con Python 3.12...

REM Cambia esta ruta a donde realmente está tu Python 3.12
set PYTHON_PATH="C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe"
call "%~dp0venv\Scripts\activate.bat"
%PYTHON_PATH% src\geforce.py

pause
