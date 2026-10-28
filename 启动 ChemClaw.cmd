@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 (
  echo Cannot open the ChemClaw project folder.
  pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo Please install Node.js 24 LTS: https://nodejs.org/
  pause
  exit /b 1
)
rem Interactive GUI picker unless --source / --info / --sync-only / --no-picker is passed.
node "%~dp0scripts\launch-chemclaw.mjs" %*
set "launch_result=%errorlevel%"
if not "%launch_result%"=="0" pause
exit /b %launch_result%
