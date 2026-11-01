import difflib
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
from reviewer.security_analyzer import analyze_with_bandit
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
# HELPERS
# --------------------------------------------------
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_error(error: Exception) -> str:
    details = f"{type(error).__name__}: {error}"

    if api_key:
        details = details.replace(api_key, "[API KEY HIDDEN]")

    return details


def new_review_state() -> dict:
    return {
        "syntax": None,
        "tools": {},
        "local_checked_at": None,
        "ai_report": None,
        "ai_error": None,
        "ai_requested_at": None,
        "ai_completed_at": None,
        "ai_seconds": None,
    }


def run_local_checks(source_code: str, state: dict) -> None:
    """Run each local analyzer separately and preserve its status."""
    state["syntax"] = check_syntax(source_code)
    state["tools"] = {}

    analyzers = {
        "Ruff": analyze_with_ruff,
        "Bandit": analyze_with_bandit,
    }

    for name, analyzer in analyzers.items():
        if not state["syntax"]["valid"]:
            state["tools"][name] = {
                "status": "skipped",
                "findings": None,
                "error": None,
            }
            continue

        try:
            findings = analyzer(source_code)

            state["tools"][name] = {
                "status": "completed",
                "findings": findings,
                "error": None,
            }

        except Exception as error:
            state["tools"][name] = {
                "status": "failed",
                "findings": None,
                "error": safe_error(error),
            }

    state["local_checked_at"] = utc_now()


def display_local_tool(name: str, result: dict) -> None:
    """Display a completed, failed, or skipped analyzer result."""
    st.markdown(f"**{name} analysis**")

    if result["status"] == "skipped":
        st.caption("Skipped because syntax checking did not pass.")
        return

    if result["status"] == "failed":
        st.error(f"{name} could not complete its analysis.")

        with st.expander(f"{name} error details"):
            st.code(result["error"], language="text")

        return

    findings = result["findings"]
    st.caption(f"Source: {name} · {len(findings)} findings")

    if not findings:
        st.info(
            f"No findings from the configured {name} checks. "
            "This does not guarantee correctness or security."
        )

    for finding in findings:
        heading = f"{finding['rule_id']} · {finding['message']}"

        with st.expander(heading, expanded=True):
            st.caption(
                f"Source: {name} · "
                f"Lines {finding['line_start']}"
                f"–{finding['line_end']}"
            )

            if name == "Bandit":
                st.write(
                    f"**Severity:** {finding['severity']} · "
                    f"**Confidence:** {finding['confidence']}"
                )

            st.code(finding["evidence"], language="python")
            st.caption("Rule-based finding requiring review.")


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

    st.caption("Ruff and Bandit work without an API key.")

    st.divider()
    st.subheader("Review engines")
    st.markdown(
        """
        - **Python:** syntax checking
        - **Ruff:** code error and quality checks
        - **Bandit:** potential security issues
        - **Gemini:** AI-assisted analysis
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
            Inspect Python code using local quality checks,
            security analysis, and AI-generated explanations.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# INPUT PANEL
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
                key="security_workspace_editor",
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

        if st.session_state.get("security_identity") != identity:
            st.session_state.security_identity = identity
            st.session_state.security_review = new_review_state()

        state = st.session_state.security_review

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
            "Submitted code is inspected, not executed."
        )


# --------------------------------------------------
# RUN ANALYSIS
# --------------------------------------------------
if local_clicked:
    run_local_checks(source_code, state)

if ai_clicked:
    state["ai_report"] = None
    state["ai_error"] = None
    state["ai_requested_at"] = None
    state["ai_completed_at"] = None
    state["ai_seconds"] = None

    run_local_checks(source_code, state)

    if state["syntax"]["valid"]:
        state["ai_requested_at"] = utc_now()

        try:
            started_at = time.perf_counter()

            with review_column:
                with st.spinner("Gemini is reviewing your code..."):
                    generated_report = review_code_structured(
                        source_code=source_code,
                        api_key=api_key,
                        model=model_name,
                    )

            state["ai_report"] = generated_report.model_dump()
            state["ai_seconds"] = round(
                time.perf_counter() - started_at,
                1,
            )
            state["ai_completed_at"] = utc_now()

        except Exception as error:
            state["ai_error"] = safe_error(error)


report = None

if state["ai_report"] is not None:
    report = ReviewReport.model_validate(state["ai_report"])


# --------------------------------------------------
# RESULTS PANEL
# --------------------------------------------------
with review_column:
    with st.container(border=True):
        st.subheader("02 · Review results")

        local_tab, ai_tab, export_tab = st.tabs(
            ["Local checks", "AI findings", "Export"]
        )

        with local_tab:
            if state["syntax"] is None:
                st.info(
                    "Select Run local checks to run "
                    "Python syntax, Ruff, and Bandit checks."
                )

            else:
                st.markdown("**Python syntax**")

                if state["syntax"]["valid"]:
                    st.success("No Python syntax errors found.")

                else:
                    st.error(state["syntax"]["message"])

                    if state["syntax"]["line"] is not None:
                        st.write(
                            f"Line: {state['syntax']['line']} · "
                            f"Column: {state['syntax']['column']}"
                        )

                for tool_name, tool_result in state["tools"].items():
                    st.divider()
                    display_local_tool(tool_name, tool_result)

        with ai_tab:
            if state["ai_error"]:
                st.error("The AI review could not be completed.")

                with st.expander("Error details", expanded=True):
                    st.code(state["ai_error"], language="text")

            elif report is not None:
                st.write(report.summary)
                st.caption(
                    f"Model requested: {model_name} · "
                    f"{state['ai_seconds']} seconds"
                )

                metric_columns = st.columns(3)

                for column, severity in zip(
                    metric_columns,
                    ["High", "Medium", "Low"],
                ):
                    count = sum(
                        finding.severity == severity
                        for finding in report.findings
                    )
                    column.metric(severity, count)

                st.caption(
                    "AI labels are judgments, not verified defects."
                )

                if not report.findings:
                    st.info("No significant AI findings reported.")

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
                    "Select Review with AI for additional analysis. "
                    "Resolve syntax errors first."
                )

        with export_tab:
            if state["syntax"] is None:
                st.info("Run local checks or an AI review first.")

            else:
                payload = {
                    "metadata": {
                        "file": file_name,
                        "source_sha256": source_hash,
                        "local_checked_at_utc": (
                            state["local_checked_at"]
                        ),
                        "model_requested": (
                            model_name
                            if state["ai_requested_at"]
                            else None
                        ),
                        "ai_requested_at_utc": (
                            state["ai_requested_at"]
                        ),
                        "ai_completed_at_utc": (
                            state["ai_completed_at"]
                        ),
                        "ai_response_seconds": state["ai_seconds"],
                    },
                    "syntax": state["syntax"],
                    "local_tools": state["tools"],
                    "ai": {
                        "review": state["ai_report"],
                        "error": state["ai_error"],
                    },
                }

                sections = [
                    "# CodeLens — Code Review",
                    f"File: {file_name}",
                    "## Python syntax",
                    state["syntax"]["message"],
                ]

                for name, result in state["tools"].items():
                    sections.append(f"## {name} analysis")

                    if result["status"] != "completed":
                        sections.append(
                            f"Status: {result['status']}. "
                            "See JSON export for diagnostics."
                        )
                        continue

                    sections.append(
                        f"{len(result['findings'])} findings."
                    )

                    for finding in result["findings"]:
                        details = (
                            f"- {finding['rule_id']} · "
                            f"Line {finding['line_start']}: "
                            f"{finding['message']}"
                        )

                        if name == "Bandit":
                            details += (
                                f" Severity: {finding['severity']}. "
                                f"Confidence: {finding['confidence']}."
                            )

                        sections.append(details)

                sections.append("## AI review")

                if report is not None:
                    sections.extend(
                        [
                            f"Model requested: {model_name}",
                            report_to_markdown(report, source_code),
                        ]
                    )

                elif state["ai_error"]:
                    sections.append(
                        "Failed. See JSON export for diagnostics."
                    )

                else:
                    sections.append("Not requested.")

                sections.append(
                    "Findings require human review. "
                    "Submitted code was not executed."
                )

                st.caption(
                    "Exports include all findings, "
                    "regardless of selected filters."
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


# --------------------------------------------------
# FULL-WIDTH CODE COMPARISON
# --------------------------------------------------
if report is not None:
    st.divider()
    st.subheader("03 · Compare proposed changes")
    st.caption(
        "Compare original source evidence with an AI-proposed snippet. "
        "The snippet may cover a different scope from the evidence range. "
        "It is not an automatic replacement or a verified patch."
    )

    proposals = [
        (index, finding)
        for index, finding in enumerate(report.findings, start=1)
        if finding.corrected_code.strip()
    ]

    if not proposals:
        st.info(
            "This review contains no proposed code snippets to compare."
        )

    else:
        proposal_labels = {
            index: f"Finding {index}: {finding.title}"
            for index, finding in proposals
        }

        selected_index = st.selectbox(
            "Choose a proposed change",
            options=list(proposal_labels),
            format_func=lambda index: proposal_labels[index],
            key=f"comparison_{source_hash}_{model_name}",
        )

        selected_finding = next(
            finding
            for index, finding in proposals
            if index == selected_index
        )

        original_snippet = "\n".join(
            source_code.splitlines()[
                selected_finding.line_start - 1:
                selected_finding.line_end
            ]
        )

        proposed_snippet = selected_finding.corrected_code

        original_column, proposed_column = st.columns(
            2,
            gap="large",
        )

        with original_column:
            st.markdown("**Original source evidence**")
            st.caption(
                f"Original file lines {selected_finding.line_start}"
                f"–{selected_finding.line_end}"
            )
            st.code(original_snippet, language="python")

        with proposed_column:
            st.markdown("**AI-proposed snippet**")
            st.caption(
                "Not executed or verified. Review before using."
            )
            st.code(proposed_snippet, language="python")

        st.markdown("**Suggested improvement**")
        st.write(selected_finding.suggested_fix)

        with st.expander("Show text differences"):
            st.caption(
                "Minus lines are original evidence; plus lines are "
                "proposed text. Diff line numbers are relative to these "
                "snippets, not the original file. Different snippet "
                "scopes can produce misleading differences; this is "
                "not an apply-ready patch."
            )

            difference = "\n".join(
                difflib.unified_diff(
                    original_snippet.splitlines(),
                    proposed_snippet.splitlines(),
                    fromfile="original_evidence",
                    tofile="ai_proposed_snippet",
                    lineterm="",
                )
            )

            if difference:
                st.code(difference, language="diff")
            else:
                st.info("The two snippets have identical lines.")

        st.download_button(
            "Download proposed snippet (.py)",
            data=proposed_snippet,
            file_name=(
                f"codelens_finding_{selected_index}_proposal.py"
            ),
            mime="text/plain",
            key="download_comparison_proposal",
        )

        st.caption(
            "The download contains only this proposed snippet, "
            "not a corrected copy of your entire file. "
            "Selecting a finding makes no new Gemini request."
        )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.divider()
st.caption(
    f"Source: {file_name} · "
    f"{len(source_code.splitlines())} lines · "
    "Python syntax + Ruff + Bandit + optional Gemini review."
)