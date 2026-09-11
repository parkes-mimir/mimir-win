# Mimir-Win

在 Linux 桌面上无缝运行 Windows 应用。

## 法律声明

- 本项目不包含 Windows 操作系统，仅提供自动化安装脚本
- 用户需要自行确保拥有合法的 Windows 许可证
- 本项目使用 MIT 许可证，与所有依赖兼容
- 使用 dockur/windows 镜像时，请遵守 Microsoft 最终用户许可协议 (EULA)
- 本项目与 Microsoft 无关联，Windows 是 Microsoft 的注册商标

## 简介

Mimir-Win 是一个 Python 工具，通过容器化（Podman/Docker）运行 Windows 虚拟机，并使用 FreeRDP 的 RemoteApp 协议将 Windows 应用无缝集成到 Linux 桌面环境中。

### 核心原理

```
Linux 主机                                Windows 虚拟机 (dockur 容器)
┌────────────────────┐   FreeRDP RDP     ┌──────────────────┐
│  mimir-win CLI     │ ────────────────► │  Guest Agent     │
│  .desktop 快捷方式 │   RemoteApp 模式  │  (PowerShell)    │
│  Wayland/X11       │   /app:program:   │  应用发现        │
└────────────────────┘                   └──────────────────┘
```

- **容器化**: 使用 `dockur/windows` 镜像在 Docker/Podman 容器中运行 Windows
- **RemoteApp**: FreeRDP 的 RAIL 协议将单个 Windows 窗口嵌入 Linux 桌面
- **Guest Agent**: Windows 内运行的 HTTP 服务器，提供应用发现和系统信息

## 系统要求

- Linux（支持 KVM 虚拟化）
- Podman 或 Docker
- FreeRDP 3+
- 4GB+ 内存，32GB+ 磁盘

## 安装

### NixOS（推荐）

#### 方式1：Flake 直接安装

```bash
# 安装到用户环境
nix profile install github:parkes-mimir/mimir-win

# 运行
mimir-win setup
mimir-win doctor
mimir-win vm start
```

#### 方式2：NixOS Module 声明式配置

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    mimir-win.url = "github:parkes-mimir/mimir-win";
  };

  outputs = { self, nixpkgs, mimir-win, ... }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        mimir-win.nixosModules.mimir-win
        {
          services."mimir-win" = {
            enable = true;
            rdp = {
              user = "MyUser";
              passwordFile = "/run/secrets/mimir-win-password";
            };
            vm = {
              cpus = 8;
              memory = "8G";
              diskSize = "128G";
              autoStart = true;
            };
            firewall = true;
          };
        }
      ];
    };
  };
}
```

#### 方式3：临时开发环境

```bash
# 进入开发环境（包含所有依赖）
nix develop github:parkes-mimir/mimir-win

# 运行
python -m mimir_win setup
python -m mimir_win vm start
```

### 非 NixOS

```bash
# 安装依赖
# Ubuntu/Debian: sudo apt install freerdp3-x11 podman
# Fedora: sudo dnf install freerdp podman
# Arch: sudo pacman -S freerdp podman

# 安装 mimir-win
pip install .

# 运行安装向导
mimir-win setup
```

## 使用方法

### CLI 命令

```bash
# 安装向导
mimir-win setup

# 环境检查
mimir-win doctor

# VM 管理
mimir-win vm start          # 启动 Windows VM
mimir-win vm stop           # 停止 VM
mimir-win vm status         # 查看状态
mimir-win vm pause          # 暂停 VM（释放 CPU）
mimir-win vm resume         # 恢复 VM

# 应用管理
mimir-win app refresh       # 从 Windows 刷新应用列表
mimir-win app list          # 列出可用应用
mimir-win app run <id>      # 启动 Windows 应用

# 运行任意 exe
mimir-win run "C:\path\to\app.exe"

# 完整桌面
mimir-win windows           # 关闭后自动刷新应用列表

# 配置
mimir-win config show       # 查看配置
mimir-win config set key val # 设置配置项
```

### 从侧边栏启动

运行 `mimir-win app refresh` 后，Windows 应用会出现在 KDE 开始菜单的 **"Mimir-Win"** 分类中，点击即可启动。

### 打开文件

```bash
# 用 Word 打开文档
mimir-win app run word ~/Documents/file.docx

# 用记事本打开
mimir-win app run notepad ~/Documents/note.txt
```

## 配置

配置文件：`~/.config/mimir-win/mimir-win.toml`

```toml
[rdp]
user = "MyWindowsUser"
password = "YOUR_PASSWORD_HERE"
ip = "127.0.0.1"
port = 3389
scale = 100

[vm]
backend = "podman"
image = "ghcr.io/dockur/windows:latest"
container_name = "Mimir-Win"
cpus = 4
memory = "4G"
disk_size = "64G"
win_version = "10"
data_dir = "/home/mimir/.local/share/mimir-win/vm"
home_share = "/home/mimir"
idle_timeout = 300
idle_action = "pause"

[display]
prefer_native_wayland = true
```

### 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `rdp.user` | `mimir` | Windows 用户名 |
| `rdp.password` | - | Windows 密码 |
| `rdp.port` | `3389` | RDP 端口 |
| `vm.backend` | `podman` | 容器后端（podman/docker） |
| `vm.cpus` | `4` | CPU 核心数 |
| `vm.memory` | `4G` | 内存大小 |
| `vm.disk_size` | `64G` | 磁盘大小 |
| `vm.win_version` | `10` | Windows 版本 |
| `vm.idle_timeout` | `300` | 空闲超时（秒） |
| `vm.idle_action` | `pause` | 超时动作（pause/stop） |
| `display.prefer_native_wayland` | `true` | 优先原生 Wayland |

## NixOS Module 选项

```nix
services."mimir-win" = {
  enable = true;                    # 启用服务
  backend = "podman";              # 容器后端
  vm = {
    cpus = 4;                      # CPU 核心数
    memory = "4G";                 # 内存大小
    diskSize = "64G";              # 磁盘大小
    winVersion = "10";             # Windows 版本
    dataDir = "/var/lib/mimir-win"; # 数据目录
    homeShare = "/home";           # 共享目录
    autoStart = true;              # 开机自动启动
    idleTimeout = 300;             # 空闲超时
    idleAction = "pause";          # 超时动作
  };
  rdp = {
    user = "mimir";                # Windows 用户名
    passwordFile = "/run/secrets/mimir-win-password";  # 密码文件
    port = 3389;                   # RDP 端口
  };
  display = {
    preferNativeWayland = true;    # 优先原生 Wayland
  };
  firewall = true;                 # 开放防火墙端口
};
```

## 架构

```
mimir-win/
├── flake.nix                    # Nix flake 入口
├── modules/
│   └── mimir-win.nix            # NixOS module
├── src/mimir_win/
│   ├── cli/                     # CLI 命令
│   │   ├── main.py              # 入口 + 子命令分发
│   │   ├── setup.py             # 交互式安装向导
│   │   ├── doctor.py            # 环境检查
│   │   ├── vm.py                # VM 管理
│   │   ├── app.py               # 应用管理
│   │   └── config_cmd.py        # 配置管理
│   ├── core/                    # 核心逻辑
│   │   ├── config.py            # TOML 配置管理
│   │   ├── vm.py                # VM 生命周期（compose 生成）
│   │   ├── rdp.py               # FreeRDP 封装
│   │   ├── display.py           # 显示环境检测
│   │   ├── daemon.py            # 空闲暂停守护
│   │   └── provisioner.py       # 首次启动自动化
│   ├── desktop/                 # 桌面集成
│   │   ├── entry.py             # .desktop 文件生成
│   │   └── icons.py             # 图标管理
│   └── guest/                   # Guest Agent 客户端
│       └── client.py            # HTTP 客户端
└── guest/                       # Windows 端文件
    ├── agent.ps1                # PowerShell HTTP Agent
    ├── install.bat              # OEM 安装脚本
    └── RDPApps.reg              # 注册表配置
```

## 工作原理

### 1. VM 管理

使用 `dockur/windows` 镜像在 Docker/Podman 容器中运行 Windows。该镜像内部使用 QEMU/KVM 进行虚拟化。

```yaml
# 自动生成的 compose.yaml
services:
  windows:
    image: ghcr.io/dockur/windows:latest
    devices:
      - /dev/kvm
    ports:
      - "127.0.0.1:3389:3389"   # RDP
      - "127.0.0.1:3390:8006"   # VNC
      - "127.0.0.1:3391:8765"   # Guest Agent
    volumes:
      - data:/storage
      - /home:/shared
      - ./oem:/oem
```

### 2. RemoteApp 窗口融合

使用 FreeRDP 的 RemoteApp（RAIL）模式，将单个 Windows 应用窗口嵌入 Linux 桌面：

```bash
xfreerdp /v:127.0.0.1:3389 /u:mimir /p:password \
    /app:program:notepad.exe,name:Notepad \
    +clipboard /sound:sys:pulse
```

### 3. Guest Agent

Windows 内运行的 PowerShell HTTP 服务器，提供：
- `/health` — 健康检查
- `/apps` — 应用发现（注册表 + 内置工具）
- `/metrics` — CPU/内存使用率

### 4. 应用发现

扫描来源：
- 内置系统工具（cmd、explorer、notepad 等）
- Windows 注册表 App Paths
- 过滤系统组件，只保留用户应用

### 5. 桌面集成

- 生成 `.desktop` 文件（KDE/GNOME 兼容）
- 提取应用图标（System.Drawing）
- 创建 KDE 菜单分类（Mimir-Win）
- 支持 MIME 类型关联

## 常见问题

### 代理问题

如果使用代理，Mimir-Win 会自动检测并配置。但某些代理可能与容器下载不兼容。如果下载失败，尝试取消代理：

```bash
unset http_proxy https_proxy all_proxy
mimir-win vm start
```

### 证书问题

重装 VM 后证书会变化，需要删除旧证书：

```bash
rm -f ~/.var/app/com.freerdp.FreeRDP/config/freerdp/server/*.pem
rm -f ~/.config/freerdp/server/*.pem
```

### Agent 不响应

如果 Guest Agent 不响应，通过 VNC 手动启动：

```powershell
# 在 VNC 的 PowerShell（管理员）中运行
Start-Process powershell -ArgumentList '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', 'C:\OEM\agent.ps1' -Verb RunAs
```

### Wayland 支持

目前 FreeRDP 的 RemoteApp 需要通过 XWayland 运行。启动应用时需要设置：

```bash
DISPLAY=:0 mimir-win app run notepad
```

FreeRDP 3.32+ 将支持原生 Wayland RAIL。

### 窗口黑屏

如果 RemoteApp 窗口黑屏，尝试使用 Flatpak 版 FreeRDP：

```bash
flatpak install flathub com.freerdp.FreeRDP
```

## 与现有项目的区别

| 特性 | WinApps | WinBoat | WinPodX | **Mimir-Win** |
|------|---------|---------|---------|---------------|
| 语言 | Shell | TypeScript/Go | Python | **Python** |
| 界面 | CLI | Electron GUI | Qt6 GUI + CLI | **CLI** |
| NixOS 模块 | ❌ | ❌ | ❌ | **✓** |
| 声明式配置 | ❌ | ❌ | ❌ | **✓** |
| 自动过滤 | ❌ | ❌ | ❌ | **✓** |
| 系统工具 | ❌ | ❌ | ❌ | **✓** |
| 关闭桌面自动刷新 | ❌ | ❌ | ❌ | **✓** |

## 开发

```bash
# 进入开发环境
nix develop

# 运行测试
python -m pytest

# 代码检查
ruff check src/
```

## 许可证

MIT
