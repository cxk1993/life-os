@echo off
REM Life-OS note bridge as Windows service (nssm Application = this cmd)
REM BRIDGE_PSK must be set by nssm AppEnvironmentExtra — do not hardcode here.
setlocal
cd /d "E:\ai work\work\life\services\bridge"
if not defined BRIDGE_PSK (
  echo BRIDGE_PSK is not set in service environment. 1>&2
  exit /b 1
)
if not defined BRIDGE_PORT set BRIDGE_PORT=8790
if not defined BRIDGE_CONFIG set BRIDGE_CONFIG=E:\ai work\work\life\services\bridge\config.yaml
"E:\ai work\work\life\services\api\.venv\Scripts\python.exe" "E:\ai work\work\life\services\bridge\serve.py"
endlocal
