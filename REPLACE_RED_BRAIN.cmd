@echo off
title Webots 5v5 Brain Simulator - Replace RED Brain
set "BRAIN_SOURCE=%~1"
if not defined BRAIN_SOURCE set /p "BRAIN_SOURCE=Brain ZIP or folder path: "
if not defined BRAIN_SOURCE exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0REPLACE_BRAIN.ps1" -Team red -Source "%BRAIN_SOURCE%"
if errorlevel 1 pause
