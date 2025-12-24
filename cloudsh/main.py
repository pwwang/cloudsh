# PYTHON_ARGCOMPLETE_OK
import sys
import asyncio
import importlib
import subprocess
from pathlib import Path

import argcomplete
from simpleconf import Config
from argx import ArgumentParser

from .utils import PACKAGE, __version__
from .commands.complete import path_completer


def create_parser() -> ArgumentParser:
    """Load all command configurations from yaml files"""
    arg_defs = {
        "prog": PACKAGE,
        "description": "Shell utilities for both local cloud files",
        "commands": [],
        "arguments": [
            {
                "flags": ["--version"],
                "help": f"Show version of {PACKAGE}",
                "action": "store_true",
            }
        ],
    }
    path_options = {}
    for argfile in Path(__file__).parent.joinpath("args").iterdir():
        cmd = argfile.stem
        cmd_args = Config.load(argfile)
        path_options[cmd] = cmd_args.pop("path_options", [])
        cmd_args.setdefault("name", cmd)
        arg_defs["commands"].append(cmd_args)

    parser = ArgumentParser.from_configs(arg_defs)
    for name, options in path_options.items():
        if isinstance(options, str):
            options = [options]
        for action in parser._actions[-1]._name_parser_map[name]._actions:
            if action.dest in options:
                action.completer = path_completer

    argcomplete.autocomplete(parser)
    return parser


def main():
    if len(sys.argv) > 3:  # cloudsh ls -- -l
        command = sys.argv[1]
        if (
            Path(__file__).parent.joinpath("commands", f"{command}.py").exists()
            and sys.argv[2] == "--"
        ):
            p = subprocess.run([command, *sys.argv[3:]])
            sys.exit(p.returncode)

    if "--version" in sys.argv:
        print(f"{PACKAGE} version: v{__version__}")
        sys.exit(0)

    args = create_parser().parse_args()
    module = importlib.import_module(f".commands.{args.COMMAND}", package=PACKAGE)
    asyncio.run(module.run(args))
