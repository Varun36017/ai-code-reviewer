import hashlib
import json
import time
from datetime import datetime, timezone

import streamlit as st

from reviewer.ai_reviewer import (
    ReviewReport,
    report_to_markdown,
    review_code_structured,
)
from reviewer.static_analyzer import analyze_with_ruff
from reviewer.syntax_checker import check_syntax


# --------------------------------------------------
# PAGE SETUP
# --------------------------------------------------
st.set_page_config(
    page_title="CodeLens | AI Code Reviewer",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# VISUAL STYLE
# --------------------------------------------------
st.markdown(
    """
    <style>
        .stApp {
            background: #f5f7fb;
        }

        .block-container {
            max-width: 1550px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        [data-testid="stSidebar"] {
            background: #101b32;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] small,
        [data-testid="stSidebar"] li,
        [data-testid="stSidebar"] li p {
            color: #e2e8f0 !important;
        }

        [data-testid="stSidebar"] hr {
            border-color: #334155;
        }

        [data-testid="stSidebar"] input {
            background: white;
            color: #0f172a;
        }

        .brand {
            color: white;
            font-size: 1.8rem;
            font-weight: 800;
        }

        .brand-note {
            color: #b9c9e2;
            line-height: 1.7;
        }

        .hero {
            background: linear-gradient(120deg, #142443, #244ea0);
            border-radius: 20px;
            padding: 28px 34px;
            margin-bottom: 24px;
        }

        .hero-tag {
            color: #a9c9ff;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.15rem;
        }

        .hero-title {
            color: white;
            font-size: clamp(1.8rem, 3vw, 2.7rem);
            font-weight: 800;
            margin: 10px 0;
        }

        .hero-description {
            color: #d5e1f5;
            line-height: 1.7;
        }

        [data-testid="stMetric"] {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 12px;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.5rem;
        }

        .stTextArea textarea {
            font-family: Consolas, "Courier New", monospace;
            font-size: 14px;
            line-height: 1.7;
        }

        button[kind="primary"] {
            background: #2563eb;
            border-color: #2563eb;
            border-radius: 10px;
            font-weight: 600;
        }

        button[kind="primary"]:hover {
            background: #1d4ed8;
            border-color: #1d4ed8;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# API CONFIGURATION
# --------------------------------------------------
api_key = ""
configuration_error = False

try:
    saved_key = st.secrets.get("GEMINI_API_KEY", "")

    if isinstance(saved_key, str):
        api_key = saved_key.strip()
    else:
        configuration_error = True

except FileNotFoundError:
    pass

except Exception:
    configuration_error = True


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------
STATE_DEFAULTS = {
    "checks_identity": None,
    "checks_report": None,
    "checks_syntax": None,
    "checks_ruff": None,
    "checks_ruff_error": None,
    "checks_ai_error": None,
    "checks_seconds": None,
    "checks_timestamp": None,
}

for key, value in STATE_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def safe_error(error: Exception) -> str:
    """Prepare diagnostic text without displaying the API key."""
    details = f"{type(error).__name__}: {error}"

    if api_key:
        details = details.replace(api_key, "[API KEY HIDDEN]")

    return details


def run_local_checks(source_code: str) -> None:
    """Run syntax and Ruff checks independently of Gemini."""
    st.session_state.checks_syntax = check_syntax(source_code)
    st.session_state.checks_ruff = None
    st.session_state.checks_ruff_error = None

    if st.session_state.checks_syntax["valid"]:
        try:
            st.session_state.checks_ruff = analyze_with_ruff(
                source_code
            )

        except Exception as error:
            st.session_state.checks_ruff_error = safe_error(error)


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div class="brand">🔎 CodeLens</div>
        <div class="brand-note">
            Understand your code.<br>
            Improve your next commit.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader("Review settings")

    model_name = st.text_input(
        "Gemini model ID",
        value="gemini-flash-latest",
    ).strip()

    if configuration_error:
        st.error("Check the format of your secrets file.")
    elif api_key:
        st.success("Saved API key loaded")
    else:
        st.warning("API key missing")

    st.caption("Local checks work without an API key.")

    st.divider()
    st.subheader("How to use")
    st.markdown(
        """
        1. Paste code or upload a Python file.
        2. Run local checks for syntax and Ruff findings.
        3. Request an AI review for additional analysis.
        4. Inspect findings and download your report.
        """
    )

    st.divider()
    st.caption(
        "Python only · Maximum input: 200 KB\n\n"
        "AI reviews send submitted code to Google's Gemini API."
    )


# --------------------------------------------------
# HEADER
# --------------------------------------------------
st.markdown(
    """
    <div class="hero">
        <div class="hero-tag">YOUR CODE REVIEW WORKSPACE</div>
        <div class="hero-title">A clearer view of your code.</div>
        <div class="hero-description">
            Combine local Python checks with AI-assisted analysis.
            See each finding's source and inspect proposed improvements.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# SOURCE PANEL
# --------------------------------------------------
input_column, review_column = st.columns(
    [1, 1.15],
    gap="large",
)

with input_column:
    with st.container(border=True):
        st.subheader("01 · Source code")

        input_method = st.radio(
            "Input method",
            ["Paste code", "Upload a file"],
            horizontal=True,
        )

        source_code = ""
        file_name = "pasted_code.py"
        input_ready = True

        if input_method == "Paste code":
            source_code = st.text_area(
                "Python code",
                value=(
                    "def calculate_average(numbers):\n"
                    "    return sum(numbers) / len(numbers)\n"
                ),
                height=380,
                key="checks_editor",
            )

            if len(source_code.encode("utf-8")) > 200_000:
                st.warning("Please keep your code under 200 KB.")
                input_ready = False

        else:
            uploaded_file = st.file_uploader(
                "Choose a Python file",
                type=["py"],
            )

            if uploaded_file is None:
                input_ready = False

            elif uploaded_file.size > 200_000:
                st.warning("Please upload a file under 200 KB.")
                input_ready = False

            else:
                file_name = uploaded_file.name

                try:
                    source_code = uploaded_file.getvalue().decode(
                        "utf-8-sig"
                    )

                    st.caption(f"Selected file: {file_name}")
                    st.code(
                        source_code,
                        language="python",
                        line_numbers=True,
                    )

                except UnicodeDecodeError:
                    st.error(
                        "Could not read the file. "
                        "Save it as UTF-8 and try again."
                    )
                    input_ready = False

        source_hash = hashlib.sha256(
            source_code.encode("utf-8")
        ).hexdigest()

        identity = (
            input_method,
            file_name,
            source_hash,
            model_name,
            input_ready,
        )

        if st.session_state.checks_identity != identity:
            for key, value in STATE_DEFAULTS.items():
                st.session_state[key] = value

            st.session_state.checks_identity = identity

        local_column, ai_column = st.columns(2)

        with local_column:
            local_clicked = st.button(
                "Run local checks",
                disabled=not input_ready,
                use_container_width=True,
            )

        with ai_column:
            ai_clicked = st.button(
                "Review with AI",
                type="primary",
                disabled=(
                    not input_ready
                    or not source_code.strip()
                    or not api_key
                    or not model_name
                ),
                use_container_width=True,
            )

        st.caption(
            "Local checks make no API requests. "
            "Submitted code is not executed."
        )


# --------------------------------------------------
# ACTIONS
# --------------------------------------------------
if local_clicked:
    run_local_checks(source_code)
    st.session_state.checks_timestamp = datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")

if ai_clicked:
    st.session_state.checks_report = None
    st.session_state.checks_ai_error = None
    st.session_state.checks_seconds = None

    run_local_checks(source_code)
    st.session_state.checks_timestamp = datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")

    if st.session_state.checks_syntax["valid"]:
        try:
            started_at = time.perf_counter()

            with review_column:
                with st.spinner("Gemini is reviewing your code..."):
                    generated_report = review_code_structured(
                        source_code=source_code,
                        api_key=api_key,
                        model=model_name,
                    )

            st.session_state.checks_report = (
                generated_report.model_dump()
            )
            st.session_state.checks_seconds = round(
                time.perf_counter() - started_at,
                1,
            )

        except Exception as error:
            st.session_state.checks_ai_error = safe_error(error)


report = None

if st.session_state.checks_report is not None:
    report = ReviewReport.model_validate(
        st.session_state.checks_report
    )


# --------------------------------------------------
# RESULTS PANEL
# --------------------------------------------------
with review_column:
    with st.container(border=True):
        st.subheader("02 · Review results")

        local_tab, ai_tab, export_tab = st.tabs(
            ["Local checks", "AI findings", "Export"]
        )

        # ------------------------------------------
        # LOCAL RESULTS
        # ------------------------------------------
        with local_tab:
            syntax_result = st.session_state.checks_syntax

            if syntax_result is None:
                st.info("Select Run local checks to begin.")

            else:
                st.markdown("**Python syntax**")

                if syntax_result["valid"]:
                    st.success("No Python syntax errors found.")

                else:
                    st.error(syntax_result["message"])

                    if syntax_result["line"] is not None:
                        st.write(
                            f"Line: {syntax_result['line']} · "
                            f"Column: {syntax_result['column']}"
                        )

                st.divider()
                st.markdown("**Ruff analysis**")

                if st.session_state.checks_ruff_error:
                    st.error("Ruff could not complete its analysis.")

                    with st.expander("Ruff error details"):
                        st.code(
                            st.session_state.checks_ruff_error,
                            language="text",
                        )

                elif st.session_state.checks_ruff is not None:
                    findings = st.session_state.checks_ruff
                    st.caption(
                        f"{len(findings)} findings · Rules: E9, F"
                    )

                    if not findings:
                        st.info(
                            "No findings from the selected Ruff rules. "
                            "This does not verify all program behavior."
                        )

                    for index, finding in enumerate(findings, 1):
                        heading = (
                            f"{finding['rule_id']} · "
                            f"{finding['message']}"
                        )

                        with st.expander(heading, expanded=True):
                            st.caption(
                                f"Source: Ruff · "
                                f"Line {finding['line_start']} · "
                                f"Column {finding['column']}"
                            )
                            st.code(
                                finding["evidence"],
                                language="python",
                            )
                            st.caption(
                                "A rule-based finding requiring review."
                            )

                else:
                    st.caption(
                        "Ruff was skipped because syntax checking "
                        "did not pass."
                    )

        # ------------------------------------------
        # AI RESULTS
        # ------------------------------------------
        with ai_tab:
            if st.session_state.checks_ai_error:
                st.error("The AI review could not be completed.")

                with st.expander("Error details", expanded=True):
                    st.code(
                        st.session_state.checks_ai_error,
                        language="text",
                    )

            elif report is not None:
                st.write(report.summary)
                st.caption(
                    f"Model requested: {model_name} · "
                    f"{st.session_state.checks_seconds} seconds"
                )

                counts = {
                    severity: sum(
                        finding.severity == severity
                        for finding in report.findings
                    )
                    for severity in ["High", "Medium", "Low"]
                }

                high_col, medium_col, low_col = st.columns(3)
                high_col.metric("High", counts["High"])
                medium_col.metric("Medium", counts["Medium"])
                low_col.metric("Low", counts["Low"])

                st.caption(
                    "AI severity labels are judgments, "
                    "not verified ratings."
                )

                if not report.findings:
                    st.info(
                        "No significant AI findings were reported. "
                        "This does not guarantee correctness."
                    )

                else:
                    severity_col, category_col = st.columns(2)

                    with severity_col:
                        severity_filter = st.selectbox(
                            "Severity",
                            ["All", "High", "Medium", "Low"],
                        )

                    with category_col:
                        category_filter = st.selectbox(
                            "Category",
                            [
                                "All",
                                "Correctness",
                                "Security",
                                "Performance",
                                "Maintainability",
                            ],
                        )

                    type_filter = st.selectbox(
                        "Finding type",
                        [
                            "All",
                            "Defect",
                            "Conditional concern",
                            "Suggestion",
                        ],
                    )

                    visible = [
                        (index, finding)
                        for index, finding in enumerate(
                            report.findings, 1
                        )
                        if (
                            severity_filter == "All"
                            or finding.severity == severity_filter
                        )
                        and (
                            category_filter == "All"
                            or finding.category == category_filter
                        )
                        and (
                            type_filter == "All"
                            or finding.finding_type == type_filter
                        )
                    ]

                    st.caption(
                        f"Showing {len(visible)} of "
                        f"{len(report.findings)} findings."
                    )

                    if not visible:
                        st.info("No findings match these filters.")

                    icons = {
                        "High": "🔴",
                        "Medium": "🟠",
                        "Low": "🔵",
                    }

                    source_lines = source_code.splitlines()

                    for index, finding in visible:
                        heading = (
                            f"{icons[finding.severity]} "
                            f"{finding.severity} · "
                            f"{index}. {finding.title}"
                        )

                        with st.expander(heading, expanded=True):
                            st.caption(
                                f"Source: Gemini · "
                                f"{finding.category} · "
                                f"{finding.finding_type} · "
                                f"Lines {finding.line_start}"
                                f"–{finding.line_end}"
                            )

                            evidence = "\n".join(
                                source_lines[
                                    finding.line_start - 1:
                                    finding.line_end
                                ]
                            )

                            st.markdown("**Source evidence**")
                            st.code(evidence, language="python")

                            st.markdown("**Why it matters**")
                            st.write(finding.explanation)

                            st.markdown("**Suggested improvement**")
                            st.write(finding.suggested_fix)

                            if finding.corrected_code.strip():
                                st.code(
                                    finding.corrected_code,
                                    language="python",
                                )
                                st.caption(
                                    "AI-generated proposal. "
                                    "Not executed or verified."
                                )

            else:
                st.info(
                    "Select Review with AI to request "
                    "additional analysis."
                )

        # ------------------------------------------
        # EXPORT
        # ------------------------------------------
        with export_tab:
            if st.session_state.checks_syntax is None:
                st.info("Run local checks or an AI review first.")

            else:
                payload = {
                    "metadata": {
                        "file": file_name,
                        "source_sha256": source_hash,
                        "model_requested": (
                            model_name
                            if (
                                report is not None
                                or st.session_state.checks_ai_error
                            )
                            else None
                        ),
                        "latest_check_at_utc": (
                            st.session_state.checks_timestamp
                        ),
                        "ai_response_seconds": (
                            st.session_state.checks_seconds
                        ),
                    },
                    "syntax": st.session_state.checks_syntax,
                    "ruff": {
                        "findings": st.session_state.checks_ruff,
                        "error": st.session_state.checks_ruff_error,
                    },
                    "ai": {
                        "review": (
                            report.model_dump()
                            if report is not None
                            else None
                        ),
                        "error": st.session_state.checks_ai_error,
                    },
                }

                sections = [
                    "# CodeLens — Code Review",
                    f"File: {file_name}",
                    "## Local check results",
                    (
                        "Syntax: "
                        f"{st.session_state.checks_syntax['message']}"
                    ),
                ]

                if st.session_state.checks_ruff_error:
                    sections.append(
                        "Ruff analysis failed. See JSON diagnostics."
                    )

                elif st.session_state.checks_ruff is not None:
                    ruff_findings = st.session_state.checks_ruff
                    sections.append(
                        f"### Ruff: {len(ruff_findings)} findings"
                    )

                    for finding in ruff_findings:
                        sections.append(
                            f"- {finding['rule_id']} · "
                            f"Line {finding['line_start']}: "
                            f"{finding['message']}"
                        )

                else:
                    sections.append("Ruff analysis was skipped.")

                if report is not None:
                    sections.extend(
                        [
                            "## AI review",
                            f"Model requested: {model_name}",
                            report_to_markdown(report, source_code),
                        ]
                    )

                elif st.session_state.checks_ai_error:
                    sections.append(
                        "## AI review\n\n"
                        "The AI review failed. See JSON diagnostics."
                    )

                else:
                    sections.append(
                        "## AI review\n\nNot requested."
                    )

                sections.append(
                    "Findings require human review. "
                    "Submitted code was not executed."
                )

                st.caption(
                    "Exports include all findings, "
                    "regardless of active filters."
                )

                st.download_button(
                    "Download Markdown report",
                    data="\n\n".join(sections),
                    file_name="codelens_review.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

                st.download_button(
                    "Download JSON report",
                    data=json.dumps(
                        payload,
                        indent=2,
                        ensure_ascii=False,
                    ),
                    file_name="codelens_review.json",
                    mime="application/json",
                    use_container_width=True,
                )


st.divider()
st.caption(
    f"Source: {file_name} · "
    f"{len(source_code.splitlines())} lines · "
    "Local rules and AI analysis provide complementary findings."
)