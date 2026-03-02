import os
import re


def refactor_skills(root_dir):
    # We look for files in skills/**/handler.py usually
    # Pattern:
    # 1. search for `class .*\(BaseSkill\):`
    # 2. search for `def input_schema\(.*\) -> Type\[(\w+)\]:` inside the class
    # 3. Replace (1) with `class .*(BaseSkill[\1]):`

    count = 0
    for root, _, files in os.walk(root_dir):
        if "venv" in root:
            continue

        for file in files:
            if not file.endswith(".py"):
                continue

            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if it inherits BaseSkill
            if "class" not in content or "(BaseSkill)" not in content:
                continue

            # Find input model type
            # looking for: def input_schema(self) -> Type[TheModel]:
            match_schema = re.search(r"def input_schema\(self\)\s*->\s*Type\[(\w+)\]:", content)
            if not match_schema:
                # Try property style without Type[] if someone did that, but standard is Type[T]
                # Or look at what execute takes: def execute(self, params: TheModel, ...
                match_exec = re.search(r"def execute\(self,\s*params:\s*(\w+)", content)
                if match_exec:
                    input_model = match_exec.group(1)
                    if input_model == "BaseModel":
                        continue  # nothing to do
                else:
                    continue
            else:
                input_model = match_schema.group(1)

            # verify input_model is likely the one
            # Replace `class Name(BaseSkill):` with `class Name(BaseSkill[InputModel]):`

            def repl(m):
                cls_name = m.group(1)
                return f"class {cls_name}(BaseSkill['input_model']):"

            new_content = re.sub(r"class (\w+)\(BaseSkill\):", repl, content)

            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Refactored {path} -> BaseSkill[{input_model}]")
                count += 1

    print(f"Total skills refactored: {count}")


if __name__ == "__main__":
    refactor_skills("skills")
