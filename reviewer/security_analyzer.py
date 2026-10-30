import json
import subprocess
import sys


MAX_SOURCE_BYTES = 200_000


def analyze_with_bandit(source_code: str) -> list[dict]:
    """Inspect source for security concerns without executing it."""

    if not source_code.strip():
        raise ValueError("Please provide some Python code.")

    if len(source_code.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("Please keep the source code under 200 KB.")

    command = [
        sys.executable,
        "-m",
        "bandit",
        "--quiet",
        "--format",
        "json",
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
            "The Bandit check exceeded its 15-second time limit."
        ) from error

    except OSError as error:
        raise RuntimeError(
            "Could not start Bandit. Check your Python environment."
        ) from error

    # Exit code 1 can indicate that Bandit found security issues.
    if completed.returncode not in (0, 1):
        details = completed.stderr.strip()

        raise RuntimeError(
            "Bandit could not complete the check. "
            f"{details or 'No diagnostic details were returned.'}"
        )

    try:
        result = json.loads(completed.stdout)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Bandit returned an unreadable analysis result."
        ) from error

    if not isinstance(result, dict):
        raise RuntimeError(
            "Bandit returned an unexpected result format."
        )

    # A failed scan must not appear as a successful zero-finding scan.
    scan_errors = result.get("errors", [])

    if scan_errors:
        reasons = "; ".join(
            str(item.get("reason", "Unknown scan error"))
            for item in scan_errors
        )

        raise RuntimeError(
            f"Bandit could not analyze the submitted code: {reasons}"
        )

    raw_findings = result.get("results")

    if not isinstance(raw_findings, list):
        raise RuntimeError(
            "Bandit did not return a valid findings list."
        )

    source_lines = source_code.splitlines()
    findings = []

    for item in raw_findings:
        line_start = item["line_number"]
        line_range = item.get("line_range") or [line_start]
        line_end = max(line_range)

        evidence = "\n".join(
            source_lines[line_start - 1 : line_end]
        )

        findings.append(
            {
                "source": "Bandit",
                "rule_id": item["test_id"],
                "rule_name": item["test_name"],
                "message": item["issue_text"],
                "severity": item["issue_severity"].title(),
                "confidence": item["issue_confidence"].title(),
                "line_start": line_start,
                "line_end": line_end,
                "evidence": evidence,
                "rule_url": item.get("more_info"),
            }
        )

    return findings