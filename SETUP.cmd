@echo off
title Webots 5v5 Brain Simulator - Setup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SETUP.ps1"
if errorlevel 1 pause
