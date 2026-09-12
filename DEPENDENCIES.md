# 依赖说明

## 核心依赖

### Python 3.10+

Mimir-Win 使用 Python 开发，需要 3.10 或更高版本。

```bash
# NixOS
nix develop  # 自动包含 Python

# Ubuntu/Debian
sudo apt install python3 python3-pip

# Fedora
sudo dnf install python3 python3-pip

# Arch
sudo pacman -S python python-pip
```

### FreeRDP 3+

远程桌面客户端，用于连接 Windows VM 的 RemoteApp 模式。

```bash
# NixOS
nix develop  # 自动包含

# Ubuntu/Debian（需要 backports）
sudo apt install freerdp3-x11

# Fedora
sudo dnf install freerdp

# Arch
sudo pacman -S freerdp

# Flatpak（推荐，兼容性最好）
flatpak install flathub com.freerdp.FreeRDP
```

**注意**：Mimir-Win 优先使用 Flatpak 版 FreeRDP，因为 NixOS 的原生版本有 RemoteApp 兼容性问题。

### Podman 或 Docker

容器运行时，用于运行 Windows VM。

```bash
# NixOS（推荐 Podman）
# 在 configuration.nix 中添加：
virtualisation.podman.enable = true;

# Ubuntu/Debian
sudo apt install podman podman-compose
# 或
sudo apt install docker.io docker-compose

# Fedora
sudo dnf install podman podman-compose

# Arch
sudo pacman -S podman podman-compose
```

**注意**：Docker Desktop 不支持，需要使用 Docker Engine。

## 可选依赖

### Flatpak

用于安装 FreeRDP。

```bash
# NixOS
# 在 configuration.nix 中添加：
services.flatpak.enable = true;

# Ubuntu/Debian
sudo apt install flatpak

# Fedora
sudo dnf install flatpak

# Arch
sudo pacman -S flatpak
```

### xrandr

用于检测显示器数量和分辨率。

```bash
# NixOS
nix develop  # 自动包含

# Ubuntu/Debian
sudo apt install x11-xserver-utils

# Fedora
sudo dnf install xrandr

# Arch
sudo pacman -S xorg-xrandr
```

### gsettings

用于检测 GNOME 桌面缩放比例。

```bash
# NixOS
nix develop  # 自动包含

# Ubuntu/Debian
sudo apt install libglib2.0-bin

# Fedora
sudo dnf install glib2

# Arch
sudo pacman -S glib2
```

### kreadconfig6 / kreadconfig5

用于检测 KDE 桌面缩放比例。

```bash
# NixOS
nix develop  # 自动包含

# Ubuntu/Debian（KDE 自带）
sudo apt install kde-config

# Fedora（KDE 自带）
sudo dnf install kde-settings

# Arch（KDE 自带）
sudo pacman -S kconfig
```

## NixOS 依赖

在 NixOS 中，所有依赖通过 Nix 管理，无需手动安装。

### 使用 Flake

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
          # 自动启用的依赖：
          # - Podman（容器运行时）
          # - KVM 内核模块
          # - 用户组配置（kvm, podman）

          services."mimir-win" = {
            enable = true;
            # ... 配置
          };
        }
      ];
    };
  };
}
```

### 自动启用的系统配置

NixOS Module 会自动启用以下配置：

```nix
# 容器运行时
virtualisation.podman.enable = true;
virtualisation.podman.dockerCompat = true;

# KVM 内核模块
boot.kernelModules = [ "kvm" "kvm-amd" "kvm-intel" ];

# 用户组
users.users.mimir-win = {
  extraGroups = [ "kvm" "podman" ];
};

# 防火墙（可选）
networking.firewall.allowedTCPPorts = [ 3389 3390 3391 ];
```

## 依赖版本要求

| 依赖 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | 3.10 | 3.12+ | 需要 `match` 语句支持 |
| FreeRDP | 3.0.0 | 3.31+ | 需要 RemoteApp 支持 |
| Podman | 4.0.0 | 5.0+ | 需要 compose 支持 |
| Docker | 20.10 | 24.0+ | 备选方案 |
| Linux Kernel | 5.10 | 6.0+ | 需要 KVM 支持 |

## 依赖检查

运行 `mimir-win doctor` 检查所有依赖：

```bash
mimir-win doctor
```

输出示例：

```
Mimir-Win 环境检查

═══════════════════════════════════════════════════════
  ✓ KVM 虚拟化          /dev/kvm 可用
  ✓ 容器后端             podman version 5.8.6
  ✓ FreeRDP 3+       /path/to/xfreerdp (v3+, flatpak)
  ✓ 配置文件             /home/user/.config/mimir-win/mimir-win.toml
  ✓ 显示环境             wayland (kde), 1 显示器
  ✓ compose 工具       podman-compose 可用
═══════════════════════════════════════════════════════

所有检查通过。
```

## 故障排除

### FreeRDP 版本过低

如果 FreeRDP 版本低于 3.0，RemoteApp 模式将无法工作。

```bash
# 检查版本
xfreerdp --version

# 解决方案：使用 Flatpak 版本
flatpak install flathub com.freerdp.FreeRDP
```

### Podman 版本过低

如果 Podman 版本低于 4.0，某些功能可能不可用。

```bash
# 检查版本
podman --version

# NixOS：更新 nixpkgs
nix flake update

# 其他发行版：参考官方文档升级
```

### KVM 不可用

```bash
# 检查 KVM
ls -la /dev/kvm

# 如果不存在，检查 BIOS 设置
# 确保启用 VT-x (Intel) 或 AMD-V (AMD)

# 检查内核模块
lsmod | grep kvm
```

### 权限问题

```bash
# 检查用户是否在 kvm 组
groups | grep kvm

# 添加用户到 kvm 组
sudo usermod -aG kvm $USER

# 重新登录生效
```
