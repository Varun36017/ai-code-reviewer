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
# SAVED API KEY
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
# New names avoid mixing old Markdown with structured data.
# --------------------------------------------------
STATE_DEFAULTS = {
    "cards_identity": None,
    "cards_report": None,
    "cards_syntax": None,
    "cards_error": None,
    "cards_seconds": None,
    "cards_timestamp": None,
}

for key, value in STATE_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


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
        st.caption("A review request verifies model access.")
    else:
        st.warning("API key missing")
        st.caption("Configure .streamlit/secrets.toml.")

    st.divider()
    st.subheader("How to use")
    st.markdown(
        """
        1. Paste code or upload a Python file.
        2. Check syntax or request an AI review.
        3. Filter findings and inspect proposed fixes.
        4. Download the complete report.
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
            Inspect findings, understand their impact,
            and explore proposed improvements.
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
                key="cards_editor",
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

        current_identity = (
            input_method,
            file_name,
            source_hash,
            model_name,
            input_ready,
        )

        if st.session_state.cards_identity != current_identity:
            for key, value in STATE_DEFAULTS.items():
                st.session_state[key] = value

            st.session_state.cards_identity = current_identity

        syntax_column, ai_column = st.columns(2)

        with syntax_column:
            syntax_clicked = st.button(
                "Check syntax",
                disabled=not input_ready,
                use_container_width=True,
            )

        with ai_column:
            review_clicked = st.button(
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
            "Syntax checks run locally. "
            "Submitted code is not executed by this app."
        )


# --------------------------------------------------
# HANDLE ACTIONS
# --------------------------------------------------
if syntax_clicked:
    st.session_state.cards_syntax = check_syntax(source_code)

if review_clicked:
    st.session_state.cards_report = None
    st.session_state.cards_error = None
    st.session_state.cards_seconds = None
    st.session_state.cards_timestamp = None

    syntax_result = check_syntax(source_code)
    st.session_state.cards_syntax = syntax_result

    if syntax_result["valid"]:
        try:
            started_at = time.perf_counter()

            with review_column:
                with st.spinner("Reviewing your Python code..."):
                    report = review_code_structured(
                        source_code=source_code,
                        api_key=api_key,
                        model=model_name,
                    )

            # Store plain data rather than a class instance.
            st.session_state.cards_report = report.model_dump()
            st.session_state.cards_seconds = round(
                time.perf_counter() - started_at,
                1,
            )
            st.session_state.cards_timestamp = datetime.now(
                timezone.utc
            ).isoformat(timespec="seconds")

        except Exception as error:
            details = f"{type(error).__name__}: {error}"

            if api_key:
                details = details.replace(
                    api_key,
                    "[API KEY HIDDEN]",
                )

            st.session_state.cards_error = details


# --------------------------------------------------
# LOAD THE CURRENT REPORT
# --------------------------------------------------
report = None

if st.session_state.cards_report is not None:
    report = ReviewReport.model_validate(
        st.session_state.cards_report
    )


# --------------------------------------------------
# RESULTS PANEL
# --------------------------------------------------
with review_column:
    with st.container(border=True):
        st.subheader("02 · Review results")

        findings_tab, syntax_tab, export_tab = st.tabs(
            ["AI findings", "Syntax check", "Export report"]
        )

        with findings_tab:
            if st.session_state.cards_error:
                st.error("The AI review could not be completed.")

                with st.expander("Error details", expanded=True):
                    st.code(
                        st.session_state.cards_error,
                        language="text",
                    )

            elif report is not None:
                st.write(report.summary)
                st.caption(
                    f"Model requested: {model_name} · "
                    f"{st.session_state.cards_seconds} seconds"
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
                    "Counts and labels reflect AI judgments, "
                    "not verified defects."
                )

                if not report.findings:
                    st.info(
                        "No significant findings were reported. "
                        "This does not guarantee correct or secure code."
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

                    visible_findings = [
                        (index, finding)
                        for index, finding in enumerate(
                            report.findings,
                            start=1,
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
                        f"Showing {len(visible_findings)} of "
                        f"{len(report.findings)} findings."
                    )

                    if not visible_findings:
                        st.info("No findings match these filters.")

                    severity_icons = {
                        "High": "🔴",
                        "Medium": "🟠",
                        "Low": "🔵",
                    }

                    source_lines = source_code.splitlines()

                    for index, finding in visible_findings:
                        icon = severity_icons[finding.severity]

                        heading = (
                            f"{icon} {finding.severity} · "
                            f"{index}. {finding.title}"
                        )

                        with st.expander(heading, expanded=True):
                            st.caption(
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
                                st.markdown("**Proposed code**")
                                st.code(
                                    finding.corrected_code,
                                    language="python",
                                )
                                st.caption(
                                    "AI-generated proposal. "
                                    "Not executed or verified."
                                )

            elif (
                st.session_state.cards_syntax is not None
                and not st.session_state.cards_syntax["valid"]
            ):
                st.warning(
                    "Fix the syntax issue before requesting "
                    "an AI review. Open Syntax check for details."
                )

            else:
                st.info(
                    "Your findings will appear here after you "
                    "select Review with AI."
                )

        with syntax_tab:
            result = st.session_state.cards_syntax

            if result is None:
                st.info("Select Check syntax to inspect your code.")

            elif result["valid"]:
                st.success(result["message"])
                st.caption(
                    "Parsing succeeded. Runtime behavior and "
                    "security have not been verified."
                )

            else:
                st.error(result["message"])

                if result["line"] is not None:
                    st.write(
                        f"**Line:** {result['line']} · "
                        f"**Column:** {result['column']}"
                    )

        with export_tab:
            if report is None:
                st.info("Complete an AI review to enable export.")

            else:
                metadata = {
                    "file": file_name,
                    "source_sha256": source_hash,
                    "model_requested": model_name,
                    "generated_at_utc": (
                        st.session_state.cards_timestamp
                    ),
                    "response_seconds": (
                        st.session_state.cards_seconds
                    ),
                }

                markdown_report = (
                    "# CodeLens — AI Code Review\n\n"
                    f"- File: {file_name}\n"
                    f"- Model requested: {model_name}\n"
                    f"- Generated at (UTC): "
                    f"{metadata['generated_at_utc']}\n\n"
                    "---\n\n"
                    f"{report_to_markdown(report, source_code)}"
                )

                json_report = json.dumps(
                    {
                        "metadata": metadata,
                        "review": report.model_dump(),
                    },
                    indent=2,
                    ensure_ascii=False,
                )

                st.write(
                    "Exports include all findings, "
                    "regardless of the selected filters."
                )

                st.download_button(
                    "Download Markdown report",
                    data=markdown_report,
                    file_name="codelens_review.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

                st.download_button(
                    "Download JSON report",
                    data=json_report,
                    file_name="codelens_review.json",
                    mime="application/json",
                    use_container_width=True,
                )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.divider()
st.caption(
    f"Source: {file_name} · "
    f"{len(source_code.splitlines())} lines · "
    "AI findings and proposed fixes require human review."
)