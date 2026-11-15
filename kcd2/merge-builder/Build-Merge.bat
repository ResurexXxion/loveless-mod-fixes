@echo off
rem KCD2 merge builder launcher (Loveless Mod Fixes). Double-click to build; nothing in the game folder changes.
rem To also install it into the game's Mods folder:  Build-Merge.bat --install
title KCD2 merge builder
cd /d "%~dp0"
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Python 3 is needed and wasn't found.
  echo Get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" when installing.
  pause
  exit /b 1
)
%PY% kcd2_merge_builder.py %*
echo.
pause
