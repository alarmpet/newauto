@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\master_setup.ps1" -PersistUserEnv -UpdateClineMcpSettings %*
