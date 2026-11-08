@echo off
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName 'FoxyGram Server' -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName 'FoxyGram Server' -Confirm:$false"
taskkill /F /IM FoxyGramServer.exe 2>nul
echo FoxyGram Server removed. Your data stays in %%LOCALAPPDATA%%\FoxyGram.
pause
