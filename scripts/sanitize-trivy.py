#!/usr/bin/env python3
"""Keep vulnerability evidence, remove secret values and source excerpts."""
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
report = json.loads(path.read_text())
secret_fields = ("RuleID", "Category", "Title", "Severity", "StartLine", "EndLine")
counts = {"vulnerabilities": 0, "secret_findings": 0}
for result in report.get("Results", []):
    counts["vulnerabilities"] += len(result.get("Vulnerabilities", []))
    if "Secrets" in result:
        counts["secret_findings"] += len(result["Secrets"])
        result["Secrets"] = [
            {**{key: secret[key] for key in secret_fields if key in secret}, "Match": "[REDACTED]"}
            for secret in result["Secrets"]
        ]
Path(sys.argv[2]).write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(counts))
