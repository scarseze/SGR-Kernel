import os
import re


def fix_dicts(root_dir):
    # Regex to find "something: dict[str, Any] =" or "-> dict[str, Any]:" or "list[dict[str, Any]]"
    # Mypy wants dict[Any, Any] or Dict[str, Any]

    # We will replace `dict` with `dict[str, Any]` in annotations.
    # Be careful not to replace `dict()` constructor calls.
    # We look for `: dict[str, Any]` or `-> dict[str, Any]` or `[dict[str, Any]]` or `, dict[str, Any]`

    # 1. ": dict[str, Any]" -> ": dict[str, Any]"
    # 2. "-> dict[str, Any]" -> "-> dict[str, Any]"
    # 3. "[dict[str, Any]]" -> "[dict[str, Any]]"
    # 4. ", dict[str, Any]" -> ", dict[str, Any]"
    # 5. "dict |" -> "dict[str, Any] |"

    patterns = [
        (r":\s*dict\b(?!\[)", ": dict[str, Any]"),
        (r"->\s*dict\b(?!\[)", "-> dict[str, Any]"),
        (r"\[\s*dict\b(?!\[)", "[dict[str, Any]"),
        (r",\s*dict\b(?!\[)", ", dict[str, Any]"),
        (r"\|\s*dict\b(?!\[)", "| dict[str, Any]"),
    ]

    count = 0
    for root, _, files in os.walk(root_dir):
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue

        for file in files:
            if not file.endswith(".py"):
                continue

            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = content
            for pat, repl in patterns:
                new_content = re.sub(pat, repl, new_content)

            # Also fix "list" to "list[Any]" if bare? No, list is usually generic but safer to leave unless error.
            # Fix "Any" import if missing?
            if "dict[str, Any]" in new_content and "from typing import Any" not in new_content:
                # Naive insert
                new_content = "from typing import Any\n" + new_content

            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Fixed dicts in {path}")
                count += 1

    print(f"Total files fixed: {count}")


if __name__ == "__main__":
    fix_dicts(".")
