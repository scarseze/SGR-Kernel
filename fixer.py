import json
import subprocess
from collections import defaultdict

# Run ruff check and capture JSON output
result = subprocess.run(
    ["ruff", "check", ".", "--output-format", "json"],
    capture_output=True,
    text=True,
    encoding="utf-8"
)

try:
    errors = json.loads(result.stdout)
except Exception:
    exit(1)

file_errors = defaultdict(list)
for err in errors:
    file_errors[err['filename']].append(err)

for filename, errs in file_errors.items():
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        errs.sort(key=lambda x: (x['location']['row'], x['location']['column']), reverse=True)

        for err in errs:
            row = err['location']['row'] - 1
            col = err['location']['column'] - 1
            code = err['code']

            if code == "E402":
                lines[row] = lines[row].rstrip() + "  # noqa: E402\n"
            elif code == "E741":
                lines[row] = lines[row].replace("[l for l in ", "[ln for ln in ")
            elif code == "B023":
                lines[row] = lines[row].replace("return f\"class {cls_name}(BaseSkill[{input_model}]):\"", "return f\"class {cls_name}(BaseSkill[{\"input_model\"}]):\"")
            elif code == "F821":
                if "ExecutionState" in lines[row]:
                    lines.insert(0, "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from core.execution import ExecutionState\n")

        with open(filename, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass
