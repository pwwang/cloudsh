# Copilot Instructions for cloudsh

## Project Overview

`cloudsh` is a Python CLI that provides drop-in replacements for GNU/Linux commands (ls, cp, mv, rm, cat, head, tail, mkdir, touch) with transparent support for cloud storage paths (GCS, S3, Azure). It uses [`cloudpathlib`](https://github.com/drivendataorg/cloudpathlib) and [`yunpath`](https://github.com/pwwang/yunpath) to abstract local and cloud file operations.

## Architecture

### Command Discovery Pattern (Critical)

Commands are **not** hardcoded. The system uses dynamic loading:

1. **TOML-driven CLI**: Each command has a `.toml` file in `cloudsh/args/` that defines its argparse configuration
2. **Dynamic import**: `main.py` scans `cloudsh/args/` directory, loads each `.toml` file via `simpleconf.Config.load()`, and builds argparse subcommands using `argx.ArgumentParser.from_configs()`
3. **Command execution**: After parsing, `importlib.import_module(f".commands.{args.COMMAND}")` dynamically imports the corresponding module from `cloudsh/commands/`

**Example**: `cloudsh/args/ls.toml` defines flags like `-l`, `-h`, `-R` → `cloudsh/commands/ls.py` implements the `run(args)` function.

### Path Completion System

- **Special field**: TOML files include `path_options` field (e.g., `path_options = ["SOURCE", "DEST"]`) to mark which arguments should use cloud path completion
- **Completion hook**: In `main.py:create_parser()`, these arguments get `action.completer = path_completer` attached
- **Caching**: Cloud path completion can use cached bucket listings (`~/.cache/cloudsh/complete.cache`) to avoid latency. See `cloudsh/commands/complete.py:_scan_path()` and `_read_cache()`

### GNU Passthrough Mode (Lines 49-55 in main.py)

**Critical feature**: `cloudsh ls -- -l` executes the native GNU `ls -l` command instead of cloudsh's implementation. This allows cloudsh to be aliased as a drop-in replacement while still accessing original commands when needed.

```python
if len(sys.argv) > 3 and sys.argv[2] == "--":
    command = sys.argv[1]
    if Path(__file__).parent.joinpath("commands", f"{command}.py").exists():
        p = subprocess.run([command, *sys.argv[3:]])
        sys.exit(p.returncode)
```

## Adding New Commands

1. Create `cloudsh/args/<command>.toml` with argparse config (see `ls.toml` or `cp.toml` as templates)
2. Create `cloudsh/commands/<command>.py` with a `run(args: Namespace) -> None` function
3. Use `AnyPath` from `yunpath` for unified local/cloud path handling
4. Set `path_options` in TOML for arguments that need path completion
5. No registration needed—dynamic discovery handles it

**Example minimal command**:
```python
# cloudsh/commands/example.py
from yunpath import AnyPath
from argx import Namespace

def run(args: Namespace) -> None:
    path = AnyPath(args.file)  # Works for both local and cloud paths
    print(path.read_text())
```

## Testing Conventions

- **Cloud testing**: Tests use real GCS bucket (`gs://handy-buffer-287000.appspot.com`) defined in `conftest.py`
- **Credentials**: Load from `.env` file via `python-dotenv` (see `tests/conftest.py`)
- **Module-level setup**: Use `setup_module()`/`teardown_module()` to create/clean test workspaces with `uuid4()` for isolation
- **Interactive mocking**: Use `monkeypatch.setattr("builtins.input", mock_input)` for testing `-i` (interactive) flags
- **Run tests**: `pytest` (configured in `pyproject.toml` with coverage)

## Dependencies and Build

- **Package manager**: Poetry (`pyproject.toml`), but generates `setup.py` for backward compatibility
- **Optional extras**: `[gcs]`, `[aws]`, `[azure]`, `[all]` for cloud provider SDKs
- **Key dependencies**:
  - `argx`: Declarative argparse from configs
  - `yunpath`: Unified Path API wrapping `pathlib.Path` and `cloudpathlib.CloudPath`
  - `python-simpleconf[toml]`: TOML config loading
  - `argcomplete`: Shell completion framework

## Common Patterns

### Error Handling
Print errors to stderr with `{PACKAGE}` prefix (e.g., `f"{PACKAGE} cp: cannot overwrite directory"`) and call `sys.exit(1)`. See `cloudsh/commands/cp.py:34-37`.

### Size Parsing
Use `utils.parse_number()` for human-readable sizes (e.g., `"1K"` → `1024`, `"1KB"` → `1000`). Supports B/KB/K/KiB/MB/M/MiB/GB/G/GiB etc.

### Cloud Path Checks
```python
from yunpath import CloudPath
if isinstance(path, CloudPath):
    # Cloud-specific handling (e.g., different copy mechanisms)
```

### Long Listing Format (`ls -l`)
Cloud paths may return `None` for `st_uid`/`st_gid`/`st_mode`. Handle gracefully with `"<unknown>"` or inferred values. See `cloudsh/commands/ls.py:_get_user_group()`.

## Development Workflow

```bash
# Install with dev dependencies
poetry install --all-extras

# Run tests (requires .env with cloud credentials)
pytest

# Test a command locally
python -m cloudsh ls /tmp
python -m cloudsh ls gs://bucket-name/

# Generate completions for testing
cloudsh complete --shell bash > /tmp/completions.bash
```

## Key Files

- `cloudsh/main.py`: Dynamic command loading and argparse setup
- `cloudsh/utils.py`: Shared utilities (version, size parsing)
- `cloudsh/args/*.toml`: Declarative CLI definitions for each command
- `cloudsh/commands/*.py`: Command implementations (each exports `run(args)`)
- `tests/conftest.py`: Test bucket configuration and credentials loading
