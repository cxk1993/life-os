@echo off
REM Life-OS nssm install — run this file as Administrator
REM Right-click -> Run as administrator, or from elevated PowerShell:
REM   cmd /c "E:\ai work\work\life\deploy\tools\nssm\install-services.cmd"

setlocal EnableExtensions
set ROOT=E:\ai work\work\life
set NSSM=%ROOT%\deploy\tools\nssm\nssm.exe
set BRIDGE_CMD=%ROOT%\services\bridge\run-bridge-service.cmd
set FRPC_CMD=%ROOT%\deploy\tools\frp\run-frpc-service.cmd
set CMD_EXE=C:\Windows\System32\cmd.exe
set STARTUP=C:\Users\lcyovo\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup

if not exist "%NSSM%" (
  echo [err] nssm not found: %NSSM%
  exit /b 1
)
if not exist "%BRIDGE_CMD%" (
  echo [err] missing %BRIDGE_CMD%
  exit /b 1
)
if not exist "%FRPC_CMD%" (
  echo [err] missing %FRPC_CMD%
  exit /b 1
)

REM ---- read BRIDGE_PSK from .env ----
set BRIDGE_PSK=
for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT%\.env") do (
  if /I "%%A"=="BRIDGE_PSK" set BRIDGE_PSK=%%B
)
if "%BRIDGE_PSK%"=="" (
  echo [err] BRIDGE_PSK not found in %ROOT%\.env
  exit /b 1
)
echo BRIDGE_PSK length OK.

REM ---- stop manual processes so ports are free ----
taskkill /F /IM frpc.exe >nul 2>&1
REM bridge python is started via cmd; kill only our venv python if command line matches serve.py
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'serve\.py|bridge\.main' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo.
echo ==== lifeos-bridge ====
"%NSSM%" stop lifeos-bridge >nul 2>&1
"%NSSM%" install lifeos-bridge "%CMD_EXE%" /c "%BRIDGE_CMD%"
"%NSSM%" set lifeos-bridge Application "%CMD_EXE%"
"%NSSM%" set lifeos-bridge AppParameters /c "%BRIDGE_CMD%"
"%NSSM%" set lifeos-bridge AppDirectory "%ROOT%\services\bridge"
"%NSSM%" set lifeos-bridge AppEnvironmentExtra BRIDGE_PSK=%BRIDGE_PSK% BRIDGE_PORT=8790 BRIDGE_CONFIG=%ROOT%\services\bridge\config.yaml
"%NSSM%" set lifeos-bridge Start SERVICE_AUTO_START
"%NSSM%" set lifeos-bridge AppStdout "%ROOT%\services\bridge\nssm-out.log"
"%NSSM%" set lifeos-bridge AppStderr "%ROOT%\services\bridge\nssm-err.log"
"%NSSM%" set lifeos-bridge AppExit Default Restart
"%NSSM%" set lifeos-bridge AppRestartDelay 3000

echo ==== lifeos-frpc ====
"%NSSM%" stop lifeos-frpc >nul 2>&1
"%NSSM%" install lifeos-frpc "%CMD_EXE%" /c "%FRPC_CMD%"
"%NSSM%" set lifeos-frpc Application "%CMD_EXE%"
"%NSSM%" set lifeos-frpc AppParameters /c "%FRPC_CMD%"
"%NSSM%" set lifeos-frpc AppDirectory "%ROOT%\deploy\tools\frp"
"%NSSM%" set lifeos-frpc Start SERVICE_AUTO_START
"%NSSM%" set lifeos-frpc AppStdout "%ROOT%\deploy\tools\frp\nssm-out.log"
"%NSSM%" set lifeos-frpc AppStderr "%ROOT%\deploy\tools\frp\nssm-err.log"
"%NSSM%" set lifeos-frpc AppExit Default Restart
"%NSSM%" set lifeos-frpc AppRestartDelay 3000

echo.
echo ==== starting ====
"%NSSM%" start lifeos-bridge
"%NSSM%" start lifeos-frpc
timeout /t 4 /nobreak >nul

echo.
echo ==== status ====
"%NSSM%" status lifeos-bridge
"%NSSM%" status lifeos-frpc
sc query lifeos-bridge | findstr STATE
sc query lifeos-frpc | findstr STATE
powershell -NoProfile -Command "Test-NetConnection 127.0.0.1 -Port 8790 -WarningAction SilentlyContinue | Select-Object -ExpandProperty TcpTestSucceeded"

if exist "%STARTUP%\lifeos-bridge.cmd" del /f /q "%STARTUP%\lifeos-bridge.cmd"
if exist "%STARTUP%\lifeos-frpc.cmd" del /f /q "%STARTUP%\lifeos-frpc.cmd"

echo.
echo Done. Logs if needed:
echo   %ROOT%\services\bridge\nssm-err.log
echo   %ROOT%\deploy\tools\frp\nssm-err.log
endlocal
