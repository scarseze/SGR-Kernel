import os
import re


def fix_types(root_dir):
    # Matches:  arg: Type = None
    # Captures:
    # 1. arg
    # 2. Type (can include [ ] . )
    # Doesn't match if | None or Optional is present

    # We read the whole file
    # We iterate line by line to be safer with regex, or use DOTALL?
    # Line by line is safer for this simple pattern.

    pattern = re.compile(r"^\s*([a-zA-Z0-9_]+)\s*:\s*([a-zA-Z0-9_\[\].]+)\s*=\s*None\s*([,)].*)?$")

    count = 0
    for root, _, files in os.walk(root_dir):
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue

        for file in files:
            if not file.endswith(".py"):
                continue

            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            modified = False

            for line in lines:
                # We strip potential comments for matching, but keep original line
                # Actually, blindly replacing might be dangerous if inside constraints or something.
                # But let's try.

                # Check directly
                match = pattern.match(line)
                if match:
                    arg_name = match.group(1)
                    type_name = match.group(2)
                    suffix = match.group(3) if match.group(3) else ""

                    if "Optional" in type_name or "Any" in type_name:
                        new_lines.append(line)
                        continue

                    # Construct new line
                    indent = line[: line.find(arg_name)]
                    new_line = f"{indent}{arg_name}: {type_name} | None = None{suffix}\n"
                    new_lines.append(new_line)
                    modified = True
                    # print(f"Fixed line in {file}: {line.strip()} -> {new_line.strip()}")
                else:
                    # Try searching within the line (e.g. for def func(arg: T | None = None)
                    # Regex for args inside parens is hard.
                    # fallback: replace simple substring " : Type = None" -> " : Type | None = None"
                    # Be careful about not replacing if it's already Correct.

                    # Heuristic: replace ": Type = None" with ": Type | None = None"
                    # But need to capture Type.

                    def repl(m):
                        t = m.group(1)
                        if "Optional" in t or "|" in t or "Any" in t:
                            return m.group(0)
                        return f": {t} | None = None"

                    # This regex matches ": Type = None" followed by comma or close paren
                    # [ ]: handles generic bracket
                    subbed = re.sub(r":\s*([a-zA-Z0-9_\[\].]+)\s*=\s*None([,)])", repl, line)
                    if subbed != line:
                        new_lines.append(subbed)
                        modified = True
                    else:
                        new_lines.append(line)

            if modified:
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                print(f"Fixed {path}")
                count += 1

    print(f"Total files fixed: {count}")


if __name__ == "__main__":
    fix_types(".")
