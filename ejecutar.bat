@echo off
rem Ejecuta Posteos desde el código fuente (crea el entorno la primera vez).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creando el entorno de Python...
    py -3 -m venv .venv || python -m venv .venv || goto :error
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)
start "" ".venv\Scripts\pythonw.exe" run.py
exit /b 0

:error
echo.
echo No se pudo preparar el entorno. Verifique que Python 3.11 o superior este instalado.
pause
exit /b 1
