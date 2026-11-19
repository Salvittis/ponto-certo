#!/usr/bin/env python3
"""Create/remove a synthetic, never-executed Semgrep finding for CI evidence.

No Git operations, credentials or deployment are performed by this helper.
"""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "security" / "controlled_finding.py"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("operation", choices=("introduce", "correct"))
args = parser.parse_args()
if args.operation == "introduce":
    if TARGET.exists():
        raise SystemExit("Fixture already exists; refusing to overwrite it.")
    TARGET.write_text(
        '# Synthetic CI evidence only. Never imported or executed.\n'
        'def unsafe_demonstration(untrusted_text):\n'
        '    return eval(untrusted_text)\n',
        encoding="utf-8",
    )
    print("Created security/controlled_finding.py. Semgrep must reject this commit.")
else:
    if not TARGET.exists():
        raise SystemExit("No controlled fixture exists; nothing was removed.")
    TARGET.unlink()
    print("Removed the synthetic defect. Re-run the unchanged pipeline.")
