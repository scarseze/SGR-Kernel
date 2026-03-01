import os


def fix_tests():
    path = "tests/test_wave3_intelligence.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # We want to replace 'for _ in range' with 'for i in range'
    # But ONLY in this file because we know 'i' was used.
    # We can just do a replace.

    new_content = content.replace("for _ in range", "for i in range")

    if new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Fixed {path}")
    else:
        print("No changes needed.")


if __name__ == "__main__":
    fix_tests()
