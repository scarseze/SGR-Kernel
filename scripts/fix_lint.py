import os
import re

REPLACEMENTS = [
    (r"result = await", "await"),
    (r"result = coord.tick", "coord.tick"),
    (r"ckpt_path = kernel", "kernel"),
    (r"events = \[\]", "# events = []"),
    (r"txt =", "_txt ="),
    (r"span =", "_span ="),
    (r"for i in", "for _ in"),
    (r"for request_id, state", "for _, state"),
    (r"for rid, state", "for _, state"),
]

FILES = [
    "tests/test_parallelism.py",
    "tests/test_replay_recon.py",
    "tests/test_agent_protocol.py",
    "tests/verify_core_model.py",
    "tests/verify_governance.py",
    "tests/test_trace_metrics.py",
    "tests/test_telemetry.py",
    "tests/test_wave3_intelligence.py",
    "tests/smoke_test_v2.py",
]


def fix_lint():
    for filepath in FILES:
        if not os.path.exists(filepath):
            print(f"Skipping {filepath} (not found)")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content
        for pattern, replacement in REPLACEMENTS:
            new_content = re.sub(pattern, replacement, new_content)

        if new_content != content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Fixed {filepath}")


if __name__ == "__main__":
    fix_lint()
