@echo off
echo Watching artin_challenge.log...
echo Press Ctrl+C to stop watching
echo.
powershell -Command "Get-Content artin_challenge.log -Wait"
