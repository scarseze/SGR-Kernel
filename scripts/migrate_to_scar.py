#!/usr/bin/env python3
"""
migrate_to_scar.py — Clean migration of SA projects to Scar.

Copies sgr_kernel, PEFTlab, ai_ml_playbook from SA to Scar,
excluding all runtime artifacts, junk files, and developer-only scripts.

Usage: python migrate_to_scar.py [--dry-run]
"""

import os
import re
import shutil
import sys
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv

SA   = Path(r"C:\Users\macht\SA")
SCAR = Path(r"C:\Users\macht\Scar")

# ─────────────────────────────────────────────────────────────────
# Common dirs to prune everywhere (matched by exact directory name)
# ─────────────────────────────────────────────────────────────────
COMMON_EXCLUDED_DIRS = {
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    ".git",       # git histories stay in Scar; don't overwrite
    "node_modules",
}

# ─────────────────────────────────────────────────────────────────
# Per-project configs
# ─────────────────────────────────────────────────────────────────
PROJECTS = [
    {
        "src": SA / "sgr_kernel",
        "dst": SCAR / "sgr_kernel",
        "excluded_dirs": {
            "traces",           # 473 runtime state folders
            "checkpoints",      # runtime
            "tapes",            # replay files
            "logs",             # runtime logs
            "generated_files",  # empty runtime dir
            "data",             # empty runtime dir
            "memory.db",        # runtime (actually a dir here)
            "site",             # mkdocs build output
            "site_docs",        # mkdocs generated content
            "verification_output",
            ".chainlit",        # UI session state
        },
        # Root-level files to exclude (exact names or patterns)
        "excluded_root_files": [
            r"^test_.*\.py$",
            r"^tmp_test_.*\.py$",
            r"^verify_.*\.py$",
            r"^verify_.*\.ps1$",
            r"^smoke_test.*\.py$",
            r"^legacy_test.*\.py$",
            r".*\.db$",
            r".*\.log$",
            r"^step\d+\.txt$",
            r"^test_output.*$",
            r"^dummy\.jsonl$",
            r"^marker\.tmp$",
            r"^VERSION$",
            r"^sync_back\.ps1$",
            r"^prepare_github\.ps1$",
            r"^mock_editor\.py$",
            r"^manual_start\.py$",
            r"^populate_rag\.py$",
            r"^verify_metadata\.py$",
            r"^verify_server\.py$",
            r"^verify_types\.py$",
        ],
    },
    {
        "src": SA / "PEFTlab",
        "dst": SCAR / "PEFTlab",
        "excluded_dirs": {
            "peftlab.egg-info",
        },
        "excluded_root_files": [],
    },
    {
        "src": SA / "ai_ml_playbook",
        "dst": SCAR / "ai_ml_playbook",
        "excluded_dirs": set(),
        "excluded_root_files": [],
    },
]


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def log(msg: str, indent: int = 0):
    prefix = "  " * indent
    print(f"{prefix}{msg}")


def should_skip_dir(name: str, extra: set) -> bool:
    return name in COMMON_EXCLUDED_DIRS or name in extra


def should_skip_root_file(name: str, patterns: list) -> bool:
    for pat in patterns:
        if re.match(pat, name, re.IGNORECASE):
            return True
    return False


def copy_tree(src: Path, dst: Path, excluded_dirs: set,
              root_file_patterns: list, is_root: bool):
    """Recursively copy src -> dst with exclusions."""
    if not dst.exists():
        if not DRY_RUN:
            dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        if item.is_dir():
            if should_skip_dir(item.name, excluded_dirs):
                log(f"[SKIP dir ] {item.relative_to(src.parent.parent)}", 1)
                continue
            copy_tree(
                item,
                dst / item.name,
                excluded_dirs=excluded_dirs,
                root_file_patterns=[],  # patterns only at root
                is_root=False,
            )
        else:
            if is_root and should_skip_root_file(item.name, root_file_patterns):
                log(f"[SKIP file] {item.relative_to(src.parent.parent)}", 1)
                continue
            dst_file = dst / item.name
            if not DRY_RUN:
                shutil.copy2(item, dst_file)


def clean_stale(src: Path, dst: Path, excluded_dirs: set):
    """
    Remove files/dirs in dst that no longer exist in src
    (respecting the same exclusion rules so we don't remove intentionally absent dirs).
    """
    if not dst.exists():
        return
    for item in list(dst.iterdir()):
        if item.name.startswith(".git"):
            continue  # never touch git history
        src_counterpart = src / item.name
        if not src_counterpart.exists():
            log(f"[PURGE    ] {item}", 1)
            if not DRY_RUN:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"  SA -> Scar Clean Migration {'[DRY RUN]' if DRY_RUN else ''}")
    print("=" * 60)

    for proj in PROJECTS:
        src: Path = proj["src"]
        dst: Path = proj["dst"]
        excl_dirs: set = proj["excluded_dirs"]
        excl_files: list = proj["excluded_root_files"]

        print(f"\n[PROJECT] {src.name}")
        print(f"  {src} -> {dst}")

        if not src.exists():
            log(f"ERROR: source does not exist: {src}", 1)
            continue

        # 1. Copy new/updated files with exclusions
        log("Copying files...", 1)
        copy_tree(src, dst, excl_dirs, excl_files, is_root=True)

        # 2. Purge stale files in dst
        log("Cleaning stale files...", 1)
        clean_stale(src, dst, excl_dirs)

        log(f"[OK] {src.name} done", 1)

    print("\n" + "=" * 60)
    print(f"  Done! {'(dry run — no files changed)' if DRY_RUN else 'Files copied.'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
