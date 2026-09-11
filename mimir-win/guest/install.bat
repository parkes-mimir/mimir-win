@echo off
REM Mimir-Win OEM Install Script
REM Runs automatically on first boot inside the dockur/windows container.

setlocal enabledelayedexpansion

echo ========================================
echo   Mimir-Win Guest Setup
echo ========================================

set WB_DIR=C:\Program Files\Mimir-Win
set OEM_DIR=C:\OEM

REM --- Create directories ---
mkdir "%WB_DIR%" 2>nul

REM --- Enable RDP ---
echo Enabling Remote Desktop...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" /v UserAuthentication /t REG_DWORD /d 0 /f

REM --- Enable RemoteApp (disable allowlist) ---
echo Enabling RemoteApp...
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Terminal Server\TSAppAllowList" /v fDisabledAllowList /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services" /v fAllowUnlistedRemotePrograms /t REG_DWORD /d 1 /f

REM --- Disable NLA (required for FreeRDP) ---
echo Disabling NLA...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" /v SecurityLayer /t REG_DWORD /d 1 /f

REM --- Open firewall for RDP and Agent ---
echo Configuring firewall...
netsh advfirewall firewall add rule name="Mimir-Win RDP" dir=in action=allow protocol=tcp localport=3389
netsh advfirewall firewall add rule name="Mimir-Win Agent" dir=in action=allow protocol=tcp localport=8765

REM --- Set UTC clock for containers ---
echo Setting UTC clock...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation" /v RealTimeIsUniversal /t REG_DWORD /d 1 /f

REM --- Disable NIC power save ---
echo Disabling NIC power save...
powershell -Command "Get-NetAdapter | Set-NetAdapterAdvancedProperty -RegistryKeyword '*EEE' -RegistryValue 0 -ErrorAction SilentlyContinue"

REM --- Install guest agent (auto-start on boot) ---
echo Installing guest agent...
if exist "%OEM_DIR%\agent.ps1" (
    REM 创建开机自启动 scheduled task（从 OEM 目录运行，保持同步）
    schtasks /create /tn "MimirWinAgent" /tr "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%OEM_DIR%\agent.ps1\"" /sc onstart /rl highest /f

    REM 立即启动 agent
    start /B powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%OEM_DIR%\agent.ps1"
)

echo.
echo ========================================
echo   Mimir-Win Guest Setup Complete
echo ========================================

endlocal
