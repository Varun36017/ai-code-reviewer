import pytest

from reviewer.security_analyzer import analyze_with_bandit
from reviewer.static_analyzer import analyze_with_ruff
from reviewer.syntax_checker import check_syntax


# --------------------------------------------------
# PYTHON SYNTAX
# --------------------------------------------------
def test_valid_python_passes_syntax_check():
    source = "total = 10\nprint(total)\n"

    result = check_syntax(source)

    assert result["valid"] is True


def test_missing_parenthesis_reports_correct_line():
    source = "total = 10\nprint(total\n"

    result = check_syntax(source)

    assert result["valid"] is False
    assert result["line"] == 2


def test_blank_input_is_rejected():
    result = check_syntax("   \n")

    assert result["valid"] is False


# --------------------------------------------------
# RUFF ANALYSIS
# --------------------------------------------------
def test_ruff_detects_undefined_name():
    source = "print(total)\n"

    findings = analyze_with_ruff(source)

    matches = [
        finding
        for finding in findings
        if finding["rule_id"] == "F821"
    ]

    assert len(matches) == 1
    assert matches[0]["source"] == "Ruff"
    assert matches[0]["line_start"] == 1
    assert matches[0]["evidence"] == "print(total)"


def test_ruff_detects_unused_import():
    source = "import math\n"

    findings = analyze_with_ruff(source)

    assert any(
        finding["rule_id"] == "F401"
        for finding in findings
    )


def test_ruff_returns_no_findings_for_corrected_example():
    source = "total = 10\nprint(total)\n"

    findings = analyze_with_ruff(source)

    assert findings == []


# --------------------------------------------------
# BANDIT SECURITY ANALYSIS
# --------------------------------------------------
def test_bandit_detects_eval():
    source = (
        "def calculate(user_input):\n"
        "    return eval(user_input)\n"
    )

    findings = analyze_with_bandit(source)

    matches = [
        finding
        for finding in findings
        if finding["rule_id"] == "B307"
    ]

    assert len(matches) == 1
    assert matches[0]["source"] == "Bandit"
    assert matches[0]["line_start"] == 2
    assert matches[0]["evidence"].strip() == (
        "return eval(user_input)"
    )


def test_bandit_returns_no_findings_for_integer_conversion():
    source = (
        "def calculate(user_input):\n"
        "    return int(user_input)\n"
    )

    findings = analyze_with_bandit(source)

    assert findings == []


# --------------------------------------------------
# INPUT LIMITS
# --------------------------------------------------
@pytest.mark.parametrize(
    "analyzer",
    [analyze_with_ruff, analyze_with_bandit],
    ids=["ruff", "bandit"],
)
def test_analyzers_reject_oversized_input(analyzer):
    source = "#" + ("x" * 200_000)

    with pytest.raises(ValueError):
        analyzer(source)