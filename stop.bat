@echo off
chcp 65001 >nul

echo =================================================================
echo        OSTANOVKA TELETHON OPS MONITOR (PORT 5050)
echo =================================================================
echo.

echo [*] Poisk i ostanovka processov na portu 5050...
set KILLED=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5050 ^| findstr LISTENING') do (
    echo [*] Zavershenie processa PID=%%a...
    taskkill /F /PID %%a >nul 2>&1
    set KILLED=1
)

if "%KILLED%"=="1" (
    echo.
    echo [+] Sluzhba na portu 5050 uspeshno ostanovlena.
) else (
    echo.
    echo [*] Aktivnyh processov na portu 5050 ne obnaruzheno.
)

echo.
ping 127.0.0.1 -n 2 >nul
