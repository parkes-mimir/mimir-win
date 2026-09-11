"""Configuration CLI commands."""

from __future__ import annotations

import argparse
import sys

from mimir_win.core.config import Config, config_dir


def handle_config(args: argparse.Namespace) -> None:
    if not hasattr(args, "config_action") or args.config_action is None:
        print("Usage: mimir-win config {set|show|path}")
        sys.exit(1)

    if args.config_action == "set":
        _cmd_set(args)
    elif args.config_action == "show":
        _cmd_show()
    elif args.config_action == "path":
        print(config_dir() / "mimir-win.toml")


def _cmd_set(args: argparse.Namespace) -> None:
    cfg = Config.load()
    key = args.key
    value = args.value

    # Parse dotted key like "rdp.user"
    parts = key.split(".", 1)
    if len(parts) != 2:
        print(f"Invalid key format: {key} (use dotted notation like rdp.user)")
        sys.exit(1)

    section, field = parts
    if section == "rdp":
        target = cfg.rdp
    elif section == "vm":
        target = cfg.vm
    elif section == "display":
        target = cfg.display
    else:
        print(f"Unknown section: {section}")
        sys.exit(1)

    if not hasattr(target, field):
        print(f"Unknown field: {key}")
        sys.exit(1)

    # Type coercion
    current = getattr(target, field)
    if isinstance(current, int):
        value = int(value)  # type: ignore[assignment]
    elif isinstance(current, bool):
        value = value.lower() in ("true", "1", "yes")  # type: ignore[assignment]

    setattr(target, field, value)
    cfg.save()
    print(f"Set {key} = {value}")


def _cmd_show() -> None:
    cfg = Config.load()
    print(f"Config: {config_dir() / 'mimir-win.toml'}\n")

    print("[rdp]")
    for k, v in cfg.rdp.__dict__.items():
        display = "****" if k == "password" and v else v
        print(f"  {k} = {display}")

    print("\n[vm]")
    for k, v in cfg.vm.__dict__.items():
        print(f"  {k} = {v}")

    print("\n[display]")
    for k, v in cfg.display.__dict__.items():
        print(f"  {k} = {v}")
