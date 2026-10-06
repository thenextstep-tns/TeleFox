@echo off
chcp 65001 >nul

echo =================================================================
echo        START TELETHON OPS MONITOR AND DISPATCHER (PORT 5050)
echo =================================================================
echo.

cd /d "%~dp0"

echo [*] Proverka porta 5050...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5050 ^| findstr LISTENING') do (
    echo [!] Port 5050 zanyat processom PID=%%a.
    echo [*] Zavershenie starogo processa...
    taskkill /F /PID %%a >nul 2>&1
)
ping 127.0.0.1 -n 2 >nul

echo.
echo [*] Zapusk sluzhby main.py na postoyannoy osnove...
echo [*] Web-panel dostupna po adresu: http://localhost:5050
echo [*] Dlya ostanovki zapustite stop.bat ili nazhmite Ctrl+C
echo.

:loop
python main.py
echo.
echo [!] Process main.py ostanovilsya. Perezapusk cherez 3 sekundy...
ping 127.0.0.1 -n 4 >nul
echo.
goto loop
