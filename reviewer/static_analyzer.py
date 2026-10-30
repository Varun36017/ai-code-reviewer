import json
import subprocess
import sys


MAX_SOURCE_BYTES = 200_000


def analyze_with_ruff(source_code: str) -> list[dict]:
    """Inspect Python code with Ruff without executing that code."""

    if not source_code.strip():
        raise ValueError("Please provide some Python code.")

    if len(source_code.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("Please keep the source code under 200 KB.")

    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--isolated",
        "--no-cache",
        "--no-fix",
        "--output-format",
        "json",
        "--select",
        "E9,F",
        "--stdin-filename",
        "submitted_code.py",
        "-",
    ]

    try:
        completed = subprocess.run(
            command,
            input=source_code,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
            shell=False,
        )

    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "The Ruff check exceeded its 15-second time limit."
        ) from error

    except OSError as error:
        raise RuntimeError(
            "Could not start Ruff. Check your Python environment."
        ) from error

    # Ruff uses exit code 1 when it successfully finds violations.
    # That is a completed analysis, not a tool failure.
    if completed.returncode not in (0, 1):
        details = completed.stderr.strip()

        raise RuntimeError(
            "Ruff could not complete the check. "
            f"{details or 'No diagnostic details were returned.'}"
        )

    try:
        raw_findings = json.loads(completed.stdout)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Ruff returned an unreadable analysis result."
        ) from error

    if not isinstance(raw_findings, list):
        raise RuntimeError("Ruff returned an unexpected result format.")

    findings = []
    source_lines = source_code.splitlines()

    for item in raw_findings:
        location = item["location"]
        end_location = item.get("end_location") or location

        line_start = location["row"]
        line_end = end_location["row"]

        evidence = "\n".join(
            source_lines[line_start - 1 : line_end]
        )

        findings.append(
            {
                "source": "Ruff",
                "rule_id": item.get("code") or "syntax-error",
                "message": item["message"],
                "line_start": line_start,
                "line_end": line_end,
                "column": location["column"],
                "evidence": evidence,
                "rule_url": item.get("url"),
            }
        )

    return findings