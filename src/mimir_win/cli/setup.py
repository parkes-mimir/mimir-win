"""Interactive setup wizard."""

from __future__ import annotations

from pathlib import Path

from mimir_win.core.config import Config, config_dir, data_dir


def run_setup(non_interactive: bool = False) -> None:
    """Run the interactive setup wizard."""
    print("=" * 50)
    print("  Mimir-Win Setup Wizard")
    print("=" * 50)
    print()

    cfg_path = config_dir() / "mimir-win.toml"
    if cfg_path.exists():
        print(f"Config file exists: {cfg_path}")
        if not non_interactive:
            answer = input("Overwrite? [y/N] ").strip().lower()
            if answer != "y":
                print("Setup cancelled.")
                return

    cfg = Config()

    # --- VM Configuration ---
    print("\n--- VM Configuration ---\n")

    cfg.vm.backend = _ask(
        "Container backend",
        default="podman",
        choices=["podman", "docker", "manual"],
        non_interactive=non_interactive,
    )
    try:
        cfg.vm.cpus = int(_ask(
            "CPU cores",
            default="4",
            non_interactive=non_interactive,
        ))
    except ValueError:
        print("  无效输入，使用默认值 4")
        cfg.vm.cpus = 4
    cfg.vm.memory = _ask(
        "RAM size",
        default="4G",
        non_interactive=non_interactive,
    )
    cfg.vm.disk_size = _ask(
        "Disk size",
        default="64G",
        non_interactive=non_interactive,
    )
    cfg.vm.win_version = _ask(
        "Windows version",
        default="11",
        choices=["11", "10", "8", "7"],
        non_interactive=non_interactive,
    )
    cfg.vm.data_dir = str(data_dir() / "vm")
    cfg.vm.home_share = str(Path.home())

    # --- RDP Configuration ---
    print("\n--- RDP Configuration ---\n")

    cfg.rdp.user = _ask(
        "Windows username",
        default="MyWindowsUser",
        non_interactive=non_interactive,
    )
    cfg.rdp.password = _ask(
        "Windows password",
        default="MyWindowsPassword",
        non_interactive=non_interactive,
        secret=True,
    )
    cfg.rdp.port = int(_ask(
        "RDP port",
        default="3389",
        non_interactive=non_interactive,
    ))

    # --- Display ---
    print("\n--- Display ---\n")

    from mimir_win.core.display import detect
    disp = detect()
    print(f"  Detected: {disp.session_type}, {disp.desktop}, {disp.scale}x scale, {disp.monitors} monitor(s)")

    cfg.vm.idle_timeout = int(_ask(
        "Idle timeout (seconds, 0=disabled)",
        default="300",
        non_interactive=non_interactive,
    ))

    # --- Save ---
    print("\n--- Saving ---\n")
    cfg.save()
    print(f"Config saved to: {cfg_path}")

    # --- Prepare OEM assets ---
    from mimir_win.core.provisioner import prepare_oem_assets
    prepare_oem_assets()
    print("OEM assets prepared")

    # --- Summary ---
    print("\n" + "=" * 50)
    print("  Setup complete!")
    print("=" * 50)
    print(f"\n  Config:    {cfg_path}")
    print(f"  Data dir:  {data_dir()}")
    print(f"  Backend:   {cfg.vm.backend}")
    print(f"  VM:        {cfg.vm.cpus} CPUs, {cfg.vm.memory} RAM, {cfg.vm.disk_size} disk")
    print("\n  Next steps:")
    print("    mimir-win doctor        Check dependencies")
    print("    mimir-win vm start      Start the Windows VM")
    print("    mimir-win app list      List installed apps")


def _ask(
    prompt: str,
    default: str = "",
    choices: list[str] | None = None,
    non_interactive: bool = False,
    secret: bool = False,
) -> str:
    """Ask the user for input."""
    if non_interactive:
        return default

    hint = ""
    if choices:
        hint = f" [{'/'.join(choices)}]"
    elif default:
        hint = f" [{default}]"

    while True:
        if secret:
            import getpass
            value = getpass.getpass(f"  {prompt}{hint}: ").strip()
        else:
            value = input(f"  {prompt}{hint}: ").strip()

        if not value and default:
            return default

        if choices and value not in choices:
            print(f"  Invalid choice. Options: {', '.join(choices)}")
            continue

        if value:
            return value

        print("  Value required")
