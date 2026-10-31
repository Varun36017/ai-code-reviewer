# Initial CodeLens AI Evaluation

## Purpose

Manually check whether the AI reviewer identifies two known concerns
and avoids reporting a concern that has already been fixed.

## Setup

- Application: CodeLens
- Requested model: gemini-flash-latest
- Method: Manual review through the Streamlit interface
- Each result below represents one observed successful response.
- The requested model is an alias; the resolved model version was not recorded.

## Results

| Case | Expected behavior | Observed behavior |
|---|---|---|
| Average without empty-input handling | Identify division by zero for an empty list | Identified ZeroDivisionError; reported lines 1–2, including the relevant line 2 |
| Average with empty-input handling | Recognize that the empty-input concern is fixed | Reported no findings |
| eval on untrusted input | Identify arbitrary code-execution risk | Identified the risk; reported lines 1–3, including the relevant line 3 |

## Observations

- The corrected average review took 110.4 seconds.
- A 503 service error occurred during testing before a successful retry.
- The unsafe-eval example included a docstring explicitly stating
  that the input came from an untrusted user.
- That example differed from cases.json: adding the docstring moved
  the eval call from line 2 to line 3.
- The first average review suggested either raising ValueError or
  returning a default value. Only raising ValueError matches the
  intended behavior recorded in cases.json.
- Proposed fixes were not executed or fully validated.

## Limitations

- Only three small examples were reviewed.
- Results were assessed manually.
- No overall accuracy, precision, or recall is claimed.
- Model responses may vary between runs.
- Broader testing is needed for larger files and different defect types.