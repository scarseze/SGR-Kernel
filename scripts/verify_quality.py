import os
import subprocess
import sys


def run_command(command, description):
    print(f"--- Running {description} ---")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, shell=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed!")
        print(e.stdout)
        print(e.stderr)
        return False


def main():
    # Ensure we are in project root
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root)

    success = True

    # 1. Ruff Lint
    if not run_command("ruff check .", "Ruff Lint Check"):
        success = False

    # 2. Ruff Format (Check only)
    if not run_command("ruff format --check .", "Ruff Format Check"):
        success = False

    # 3. Mypy Type Check
    if not run_command("mypy .", "Mypy Type Check"):
        success = False

    if success:
        print("\n✨ All quality checks passed!")
        sys.exit(0)
    else:
        print("\n⚠️ Some quality checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
