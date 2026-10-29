import ast


def check_syntax(source_code: str) -> dict:
    """Check Python syntax without executing the submitted code."""

    if not source_code.strip():
        return {
            "valid": False,
            "message": "Please provide some Python code.",
            "line": None,
            "column": None,
        }

    try:
        ast.parse(source_code)

        return {
            "valid": True,
            "message": "No Python syntax errors found.",
            "line": None,
            "column": None,
        }

    except SyntaxError as error:
        return {
            "valid": False,
            "message": error.msg,
            "line": error.lineno,
            "column": error.offset,
        }