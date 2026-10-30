@echo off
setlocal

title Offline-Mod-3D-Pruefung
if "%~1"=="" (
  echo Ziehe eine Mod-ZIP-Datei auf diese Datei, um sie zu pruefen.
  echo.
  pause
  exit /b 2
)

where py >nul 2>&1
if errorlevel 1 (
  python "%~dp0inspect_mod_3d.py" "%~f1" --open
) else (
  py -3 "%~dp0inspect_mod_3d.py" "%~f1" --open
)

if errorlevel 1 (
  echo.
  echo Die Pruefung meldet mindestens einen Fehler. Der HTML-Bericht wurde trotzdem erstellt.
  echo Bitte den geoeffneten Bericht lesen.
)
echo.
pause
