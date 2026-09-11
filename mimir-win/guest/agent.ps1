param([int]$Port = 8765)
$ErrorActionPreference = "Continue"

function Get-AppIcon {
    param([string]$ExePath)
    try {
        if (-not (Test-Path $ExePath)) { return "" }
        Add-Type -AssemblyName System.Drawing
        $icon = [System.Drawing.Icon]::ExtractAssociatedIcon($ExePath)
        if ($null -eq $icon) { return "" }
        $bmp = $icon.ToBitmap()
        $ms = New-Object System.IO.MemoryStream
        $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        $bytes = $ms.ToArray()
        $ms.Dispose()
        $bmp.Dispose()
        $icon.Dispose()
        return [Convert]::ToBase64String($bytes)
    } catch {
        return ""
    }
}

function Get-InstalledApps {
    $apps = @()
    $seen = @{}

    $builtin = @(
        @{Name="Command Prompt"; Path="C:\Windows\System32\cmd.exe"},
        @{Name="File Explorer"; Path="C:\Windows\explorer.exe"},
        @{Name="Notepad"; Path="C:\Windows\System32\notepad.exe"},
        @{Name="Paint"; Path="C:\Windows\System32\mspaint.exe"},
        @{Name="Calculator"; Path="C:\Windows\System32\calc.exe"},
        @{Name="WordPad"; Path="C:\Program Files\Windows NT\Accessories\wordpad.exe"},
        @{Name="Snipping Tool"; Path="C:\Windows\system32\SnippingTool.exe"},
        @{Name="Remote Desktop"; Path="C:\Windows\System32\mstsc.exe"},
        @{Name="Registry Editor"; Path="C:\Windows\regedit.exe"},
        @{Name="Task Manager"; Path="C:\Windows\System32\Taskmgr.exe"},
        @{Name="Control Panel"; Path="C:\Windows\System32\control.exe"},
        @{Name="System Info"; Path="C:\Windows\System32\msinfo32.exe"},
        @{Name="Disk Management"; Path="C:\Windows\System32\diskmgmt.msc"},
        @{Name="Device Manager"; Path="C:\Windows\System32\devmgmt.msc"}
    )
    foreach ($item in $builtin) {
        if (Test-Path $item.Path) {
            $seen[$item.Path] = $true
            $icon = Get-AppIcon -ExePath $item.Path
            $apps += @{
                Name = $item.Name
                Path = $item.Path
                Source = "builtin"
                Icon = $icon
            }
        }
    }

    $paths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    )
    foreach ($regPath in $paths) {
        if (-not (Test-Path $regPath)) { continue }
        Get-ChildItem $regPath -ErrorAction SilentlyContinue | ForEach-Object {
            $name = $_.PSChildName -replace '\.exe$', ''
            $default = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).'(default)'
            if ($default -and (Test-Path $default -ErrorAction SilentlyContinue)) {
                if ($seen.ContainsKey($default)) { return }
                $seen[$default] = $true
                $info = Get-Item $default -ErrorAction SilentlyContinue
                $desc = ""
                try { $desc = $info.VersionInfo.FileDescription } catch {}
                $icon = Get-AppIcon -ExePath $default
                $apps += @{
                    Name = if ($desc) { $desc } else { $name }
                    Path = $default
                    Source = "registry"
                    Icon = $icon
                }
            }
        }
    }
    return $apps
}

$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add("http://127.0.0.1:$Port/")
try { $listener.Start(); Write-Host "Agent listening on port $Port" } catch { Write-Host "Failed: $_"; exit 1 }

while ($listener.IsListening) {
    try {
        $ctx = $listener.GetContext()
        $req = $ctx.Request
        $resp = $ctx.Response
        $path = $req.Url.AbsolutePath
        $code = 200
        $body = ""
        switch ($path) {
            "/health" { $body = '{"status":"ok"}' }
            "/apps" { $body = (Get-InstalledApps | ConvertTo-Json -Depth 3) }
            "/metrics" {
                $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
                $os = Get-CimInstance Win32_OperatingSystem
                $memTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
                $memFree = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
                $memUsed = [math]::Round($memTotal - $memFree, 2)
                $body = @{
                    cpu_percent = [int]$cpu
                    memory_total_gb = $memTotal
                    memory_used_gb = $memUsed
                    memory_percent = [math]::Round(($memUsed / $memTotal) * 100, 1)
                } | ConvertTo-Json
            }
            default { $code = 404; $body = '{"error":"not found"}' }
        }
        $resp.StatusCode = $code
        $resp.ContentType = "application/json"
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $resp.ContentLength64 = $bytes.Length
        $resp.OutputStream.Write($bytes, 0, $bytes.Length)
        $resp.OutputStream.Close()
    } catch { Write-Host "Error: $_" }
}
