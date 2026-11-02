# CodeLens — Python Code Reviewer

[![CodeLens tests](https://github.com/Varun36017/ai-code-reviewer/actions/workflows/tests.yml/badge.svg)](https://github.com/Varun36017/ai-code-reviewer/actions/workflows/tests.yml)

CodeLens combines local Python checks with Gemini-assisted code reviews
in a Streamlit workspace. Users can inspect findings, compare proposed
changes, and download review reports.

Submitted Python code is analyzed, not executed.

## Features

- Paste Python code or upload a UTF-8 `.py` file.
- Check Python syntax and display error locations.
- Detect code issues using Ruff's configured `E9` and `F` rules.
- Identify potential security issues using Bandit.
- Request structured AI reviews from Gemini.
- Filter AI findings by severity, category, and finding type.
- View source evidence, explanations, and suggested improvements.
- Compare original evidence and proposed snippets side by side.
- View text differences and download proposed snippets.
- Export complete findings as Markdown or JSON.
- Clear previous results when the input or model changes.
- Handle API failures with readable messages and bounded retries.

The maximum submitted input size is 200,000 bytes.

## Review engines

| Engine | Purpose | Requires Gemini API access |
|---|---|---|
| Python `ast` | Syntax parsing | No |
| Ruff | Configured code error and quality checks | No |
| Bandit | Potential security issues | No |
| Gemini | Contextual analysis and explanations | Yes |

Local checks remain available without a Gemini API key.
A failure in one local analyzer is reported separately from the others.

## Technology

- Python
- Streamlit
- Google Gen AI SDK
- Pydantic
- Ruff
- Bandit
- pytest
- GitHub Actions

## Getting started

The project has been tested locally on Windows with Python 3.14.
The GitHub Actions workflow also uses Python 3.14.

### 1. Clone the repository

```powershell
git clone https://github.com/Varun36017/ai-code-reviewer.git
cd ai-code-reviewer
```

### 2. Create a virtual environment

```powershell
py -3.14 -m venv .venv
```

### 3. Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Configure Gemini

Create a folder named `.streamlit` in the project root if it does
not already exist.

Inside it, create `secrets.toml`:

```toml
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
```

Replace the placeholder with your own key.

The `.streamlit/secrets.toml` file is excluded by `.gitignore`.
Do not commit API keys or include them in screenshots.

The key is stored as plaintext in this local file; it is not
encrypted by the application.

### 5. Start the application

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed in the terminal.

## Using CodeLens

1. Paste Python code or upload a `.py` file.
2. Select **Run local checks** to run syntax, Ruff, and Bandit checks.
3. To request an AI review, enter an available Gemini model ID in
   the sidebar and select **Review with AI**.
4. Inspect results in **Local checks** and **AI findings**.
5. Scroll to **Compare proposed changes** when the review includes
   proposed code.
6. Use **Export** to download the complete review.

AI reviews run local checks first. Syntax errors must be resolved
before the Gemini request is sent.

Changing filters or selecting a proposed snippet does not make
another Gemini request.

### Example input

```python
def calculate_average(numbers):
    return sum(numbers) / len(numbers)
```

The AI may identify that an empty collection causes division by zero.
The appropriate fix depends on the function's intended behavior.

## Gemini configuration and reliability

The sidebar defaults to `gemini-flash-latest`, which was used in the
initial manual evaluation. Model availability and access can change.

Use a model available to your project that supports structured
JSON responses. Listing a model does not guarantee that generation
requests will succeed.

The AI reviewer configures:

- A 45-second network timeout per request attempt.
- At most two attempts, including the original request.
- A retry for selected temporary HTTP failures:
  `408`, `500`, `502`, `503`, and `504`.
- Readable messages for authentication, access, model availability,
  quota, connection, and response-format errors.

The timeout is not a strict overall duration limit. Retries and
network overhead can make the total wait longer than 45 seconds.

API usage may incur charges depending on the project's billing
and usage settings.

## Tests

Install development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run the local analyzer tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_analyzers.py -v
```

The current suite contains 10 test cases covering:

- Valid Python syntax.
- Missing-parenthesis line reporting.
- Blank-input rejection.
- Ruff detection of undefined names and unused imports.
- A corrected example with no configured Ruff findings.
- Bandit detection of `eval`.
- An integer-conversion example with no Bandit findings.
- Oversized-input rejection by both analyzers.

These tests do not require Gemini API access.

GitHub Actions runs the suite on pushes and pull requests.
The workflow can also be started manually.

Passing tests demonstrate the covered behavior; they do not
guarantee that the entire application is bug-free.

## Initial AI evaluation

Three small examples were reviewed manually:

| Example | Observed result |
|---|---|
| Average without empty-input handling | Identified the division-by-zero concern |
| Average with empty-input handling | Reported no findings |
| `eval` on explicitly untrusted input | Identified arbitrary code-execution risk |

See [evaluation/cases.json](evaluation/cases.json) for the initial
cases and [evaluation/initial_results.md](evaluation/initial_results.md)
for observations and limitations.

The manually reviewed `eval` example included an additional docstring
describing the input as untrusted. This moved the relevant call to
line 3, compared with line 2 in the initial cases file.

These observations are not an overall accuracy measurement.
The evaluation is small, manually assessed, and has not established
precision, recall, or performance across larger projects.

## Project structure

```text
app.py                         Streamlit interface
requirements.txt               Application dependencies
requirements-dev.txt           Development dependencies
list_models.py                 Model-listing utility

reviewer/
    __init__.py
    syntax_checker.py          Python syntax checking
    static_analyzer.py         Ruff integration
    security_analyzer.py       Bandit integration
    ai_reviewer.py             Structured Gemini reviews

tests/
    test_local_analyzers.py     Local analyzer tests

evaluation/
    cases.json                 Initial evaluation cases
    initial_results.md         Manual evaluation observations

examples/
    hello.py                   Valid example
    syntax_error.py            Intentionally invalid example

.streamlit/
    config.toml                Application theme
    secrets.toml               Local API key; not committed

.github/
    workflows/
        tests.yml              Automated test workflow
```

## Privacy and limitations

- Local checks do not send submitted source code to Gemini.
- Selecting **Review with AI** sends submitted source code to
  Google's Gemini API.
- Submitted code is not executed by CodeLens.
- AI findings may be incorrect, incomplete, or dependent on
  unstated requirements.
- Severity labels are judgments, not verified defects.
- No findings does not guarantee correctness or security.
- Proposed snippets are not executed or verified.
- Source evidence and proposed snippets may cover different scopes.
  The displayed diff is not an automatically applicable patch.
- Downloaded proposals contain snippets, not necessarily a complete
  corrected file.
- API availability, quotas, and latency can affect AI reviews.
- Current analysis is limited to one Python file at a time.

Review and test proposed changes before using them.

## Future work

- Expand the evaluation dataset and record repeatable results.
- Add automated tests for AI error handling and response validation.
- Support review context such as intended inputs and requirements.
- Add follow-up questions about review findings.
- Explore multi-file analysis.
- Prepare a hosted demonstration.