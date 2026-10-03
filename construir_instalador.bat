@echo off
rem Genera dist\Posteos\Posteos.exe y, si Inno Setup 6 esta instalado, el instalador.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv || python -m venv .venv || goto :error
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt || goto :error
".venv\Scripts\python.exe" -m PyInstaller packaging\posteos.spec --noconfirm || goto :error

for /f %%v in ('".venv\Scripts\python.exe" -m posteos --version') do set VERSION=%%v
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% /DVersion=%VERSION% packaging\instalador.iss || goto :error
    echo.
    echo Instalador generado en dist\instalador
) else (
    echo.
    echo Inno Setup 6 no esta instalado: se genero solo la carpeta dist\Posteos.
)
pause
exit /b 0

:error
echo.
echo Hubo un error durante la compilacion.
pause
exit /b 1
