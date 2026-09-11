{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.services."mimir-win";

  # 计算端口
  rdpPort = cfg.rdp.port;
  vncPort = rdpPort + 1;
  agentPort = rdpPort + 2;

  # 数据目录
  dataDir = cfg.vm.dataDir;
  oemDir = "${dataDir}/oem";

  # 从包中复制 Guest Agent 资产
  guestAssets = pkgs.runCommand "mimir-win-guest-assets" { } ''
    mkdir -p $out
    cp -r ${cfg.package}/share/mimir-win/guest/* $out/
    chmod -R u+w $out
  '';

  # compose.yaml 生成 - 声明式（密码通过环境变量传递，不写入文件）
  composeYaml = pkgs.writeText "mimir-win-compose.yaml" ''
    name: "mimir-win"
    services:
      windows:
        image: ${cfg.vm.image}
        container_name: Mimir-Win
        environment:
          VERSION: "${cfg.vm.winVersion}"
          RAM_SIZE: "${cfg.vm.memory}"
          CPU_CORES: "${toString cfg.vm.cpus}"
          DISK_SIZE: "${cfg.vm.diskSize}"
          USERNAME: "${cfg.rdp.user}"
          PASSWORD: "$PASSWORD"
        devices:
          - /dev/kvm
          - /dev/net/tun
        cap_add:
          - NET_ADMIN
          - SYS_ADMIN
        security_opt:
          - seccomp:unconfined
        ports:
          - "127.0.0.1:${toString rdpPort}:3389/tcp"
          - "127.0.0.1:${toString rdpPort}:3389/udp"
          - "127.0.0.1:${toString vncPort}:8006"
          - "127.0.0.1:${toString agentPort}:8765/tcp"
        volumes:
          - ${dataDir}/vm:/storage
          ${if cfg.vm.homeShare == "" then "# homeShare not configured" else "- ${cfg.vm.homeShare}:/shared"}
          - ${oemDir}:/oem
  '';

  # 完整配置文件
  configFile = pkgs.writeText "mimir-win.toml" ''
    debug = false

    [rdp]
    user = "${cfg.rdp.user}"
    password_file = "${cfg.rdp.passwordFile}"
    port = ${toString rdpPort}

    [vm]
    backend = "${cfg.backend}"
    image = "${cfg.vm.image}"
    container_name = "Mimir-Win"
    cpus = ${toString cfg.vm.cpus}
    memory = "${cfg.vm.memory}"
    disk_size = "${cfg.vm.diskSize}"
    win_version = "${cfg.vm.winVersion}"
    data_dir = "${dataDir}/vm"
    home_share = "${if cfg.vm.homeShare == "" then "" else cfg.vm.homeShare}"
    auto_start = ${boolToString cfg.vm.autoStart}
    idle_timeout = ${toString cfg.vm.idleTimeout}
    idle_action = "${cfg.vm.idleAction}"

    [display]
    prefer_native_wayland = ${boolToString cfg.display.preferNativeWayland}
  '';

  # 启动脚本 - 处理 secret、OEM 资产、compose 生成
  startScript = pkgs.writeShellScript "mimir-win-start" ''
    set -euo pipefail

    # 创建数据目录
    mkdir -p "${dataDir}/vm" "${oemDir}"

    # 复制 OEM 资产（Guest Agent、install.bat、注册表）
    cp -f ${guestAssets}/* "${oemDir}/" 2>/dev/null || true
    chmod -R u+rw "${oemDir}"

    # 复制 compose.yaml
    cp -f ${composeYaml} "${dataDir}/vm/compose.yaml"

    # 从 secret 文件读取密码，通过环境变量传递
    export PASSWORD="$(cat ${cfg.rdp.passwordFile})"

    # 启动容器（密码通过环境变量传递，不写入文件）
    ${if cfg.backend == "podman" then "podman-compose" else "docker compose"} \
      --file "${dataDir}/vm/compose.yaml" up -d
  '';

  # 停止脚本
  stopScript = pkgs.writeShellScript "mimir-win-stop" ''
    ${if cfg.backend == "podman" then "podman-compose" else "docker compose"} \
      --file "${dataDir}/vm/compose.yaml" down 2>/dev/null || true
  '';
in
{
  options.services."mimir-win" = {
    enable = mkEnableOption "Mimir-Win - 在 Linux 桌面上无缝运行 Windows 应用";

    package = mkOption {
      type = types.package;
      default = pkgs.mimir-win or (pkgs.callPackage ../packages/mimir-win { });
      description = "Mimir-Win 包。";
    };

    backend = mkOption {
      type = types.enum [ "podman" "docker" ];
      default = "podman";
      description = "容器后端：podman 或 docker。";
    };

    vm = {
      image = mkOption {
        type = types.str;
        default = "ghcr.io/dockur/windows:latest";
        description = "Windows VM 容器镜像。";
      };

      cpus = mkOption {
        type = types.int;
        default = 4;
        description = "分配给 VM 的 CPU 核心数。";
      };

      memory = mkOption {
        type = types.str;
        default = "4G";
        description = "分配给 VM 的内存大小（如 4G, 8G）。";
      };

      diskSize = mkOption {
        type = types.str;
        default = "64G";
        description = "VM 磁盘大小（如 64G, 128G）。";
      };

      winVersion = mkOption {
        type = types.enum [ "11pro" "11" "10" "8" "7" ];
        default = "11pro";
        description = "Windows 版本。11pro 支持 RemoteApp，11 可能是家庭版。";
      };

      dataDir = mkOption {
        type = types.path;
        default = "/var/lib/mimir-win";
        description = "VM 数据存储目录（磁盘镜像、compose 文件等）。";
      };

      homeShare = mkOption {
        type = types.str;
        default = "/home";
        description = "与 Windows 共享的目录路径。默认共享 /home。设为空字符串禁用。";
      };

      autoStart = mkEnableOption "开机自动启动 Windows VM。";

      idleTimeout = mkOption {
        type = types.int;
        default = 300;
        description = "空闲超时秒数，超时后自动暂停 VM。0 = 禁用。";
      };

      idleAction = mkOption {
        type = types.enum [ "pause" "stop" ];
        default = "pause";
        description = "空闲超时动作。pause = 暂停（保留内存），stop = 关机（释放内存）。";
      };
    };

    rdp = {
      user = mkOption {
        type = types.str;
        default = "Administrator";
        description = "Windows RDP 用户名。";
      };

      passwordFile = mkOption {
        type = types.path;
        description = "包含 Windows RDP 密码的文件路径（配合 sops-nix/agenix 使用）。";
      };

      port = mkOption {
        type = types.port;
        default = 3389;
        description = "RDP 端口。VNC 端口自动为 port+1，Agent 端口自动为 port+2。";
      };
    };

    display = {
      preferNativeWayland = mkOption {
        type = types.bool;
        default = true;
        description = "优先使用原生 Wayland FreeRDP 客户端（3.32+）。";
      };
    };

    firewall = mkEnableOption "开放 RDP 和 VNC 防火墙端口。";
  };

  config = mkIf cfg.enable (mkMerge [
    # ============================================================
    # 基础配置：用户、组、包
    # ============================================================
    {
      assertions = [
        {
          assertion = cfg.rdp.passwordFile != null;
          message = ''services."mimir-win".rdp.passwordFile 必须设置。'';
        }
      ];

      # 系统用户
      users.users.mimir-win = {
        isSystemUser = true;
        group = "mimir-win";
        extraGroups = [ "kvm" ]
          ++ optional (cfg.backend == "podman") "podman"
          ++ optional (cfg.backend == "docker") "docker";
      };
      users.groups.mimir-win = { };

      # 安装包到系统
      environment.systemPackages = [ cfg.package ];

      # KVM 内核模块
      boot.kernelModules = [ "kvm" ] ++
        optional (pkgs.stdenv.hostPlatform.isx86) "kvm-intel" ++
        optional (pkgs.stdenv.hostPlatform.isx86) "kvm-amd";
    }

    # ============================================================
    # 容器后端
    # ============================================================
    (mkIf (cfg.backend == "podman") {
      virtualisation.podman = {
        enable = true;
        dockerCompat = true;
        defaultNetwork.settings.dns_enabled = true;
      };
    })
    (mkIf (cfg.backend == "docker") {
      virtualisation.docker.enable = true;
    })

    # ============================================================
    # systemd 服务 - 开箱即用
    # ============================================================
    {
      systemd.services.mimir-win = {
        description = "Mimir-Win Windows VM";
        wantedBy = optional cfg.vm.autoStart "multi-user.target";
        after = [ "network-online.target" ]
          ++ optional (cfg.backend == "podman") "podman.service"
          ++ optional (cfg.backend == "docker") "docker.service";
        wants = [ "network-online.target" ];

        # 环境变量：指向配置文件
        environment = {
          MIMIR_WIN_CONFIG = "/etc/mimir-win/mimir-win.toml";
        };

        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          User = "mimir-win";
          Group = "mimir-win";

          # 启动：自动处理 compose、OEM 资产、密码
          ExecStart = "${startScript}";
          ExecStop = "${stopScript}";

          # 超时
          TimeoutStartSec = 600;  # 首次安装可能很慢
          TimeoutStopSec = 60;

          # 重启策略
          Restart = "on-failure";
          RestartSec = 30;

          # 安全限制
          ProtectSystem = "strict";
          ProtectHome = false;  # 需要访问 home 目录做文件共享
          ReadWritePaths = [ dataDir ];
          PrivateTmp = true;
        };
      };

      # 配置文件
      environment.etc."mimir-win/mimir-win.toml" = {
        source = configFile;
        mode = "0640";
        group = "mimir-win";
      };
    }

    # ============================================================
    # 防火墙
    # ============================================================
    (mkIf cfg.firewall {
      networking.firewall.allowedTCPPorts = [
        rdpPort
        vncPort
        agentPort
      ];
    })
  ]);
}
