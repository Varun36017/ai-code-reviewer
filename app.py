import hashlib
import time
from datetime import datetime, timezone

import streamlit as st

from reviewer.ai_reviewer import review_code
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
# Only static, application-owned HTML is used here.
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
        [data-testid="stSidebar"] small {
            color: #e2e8f0;
        }

        [data-testid="stSidebar"] hr {
            border-color: #334155;
        }

        [data-testid="stSidebar"] input {
            background: #ffffff;
            color: #0f172a;
        }

        .brand {
            color: #ffffff;
            font-size: 1.8rem;
            font-weight: 800;
            letter-spacing: -0.05rem;
            margin-bottom: 0.25rem;
        }

        .brand-note {
            color: #a9b8d0;
            font-size: 0.9rem;
            line-height: 1.6;
        }

        .hero {
            background: linear-gradient(120deg, #142443, #244ea0);
            border-radius: 20px;
            padding: 30px 34px;
            margin-bottom: 24px;
        }

        .hero-tag {
            color: #a9c9ff;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.15rem;
            margin-bottom: 10px;
        }

        .hero-title {
            color: #ffffff;
            font-size: clamp(1.8rem, 3vw, 2.7rem);
            font-weight: 800;
            letter-spacing: -0.07rem;
            line-height: 1.2;
            margin-bottom: 12px;
        }

        .hero-description {
            color: #d5e1f5;
            font-size: 1rem;
            line-height: 1.65;
            max-width: 760px;
        }

        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 16px 20px;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.5rem;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px;
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

        [data-testid="stDownloadButton"] button {
            border-radius: 10px;
        }

        .empty-state {
            padding: 48px 20px;
            text-align: center;
        }

        .empty-icon {
            font-size: 2.4rem;
            margin-bottom: 12px;
        }

        .empty-title {
            color: #172554;
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .empty-description {
            color: #64748b;
            line-height: 1.7;
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
defaults = {
    "workspace_identity": None,
    "syntax_result": None,
    "ai_review": None,
    "ai_error": None,
    "review_seconds": None,
    "review_timestamp": None,
}

for state_key, default_value in defaults.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div class="brand">🔎 CodeLens</div>
        <div class="brand-note">
            AI code review<br>
            Understand your code. Improve your next commit.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader("Review settings")

    model_name = st.text_input(
        "Gemini model ID",
        value="gemini-flash-latest",
        help="Use a model ID tested with your API project.",
    ).strip()

    if configuration_error:
        st.error("Check the format of your secrets file.")
    elif api_key:
        st.success("Saved API key loaded")
        st.caption("Key presence checked. Requests verify access.")
    else:
        st.warning("API key missing")
        st.caption(
            "Add GEMINI_API_KEY to .streamlit/secrets.toml."
        )

    st.divider()
    st.subheader("How to use")

    st.write("1. Paste code or upload a Python file.")
    st.write("2. Check syntax or start an AI review.")
    st.write("3. Read the findings and export your report.")

    st.divider()
    st.caption(
        "Python files only · 200 KB input limit\n\n"
        "AI reviews send submitted code to Google's Gemini API."
    )


# --------------------------------------------------
# HEADER
# --------------------------------------------------
st.markdown(
    """
    <div class="hero">
        <div class="hero-tag">YOUR CODE REVIEW WORKSPACE</div>
        <div class="hero-title">
            A clearer view of your code.
        </div>
        <div class="hero-description">
            Check Python syntax, explore potential bugs,
            and get explanations that help you understand
            what to improve and why.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# WORKSPACE LAYOUT
# --------------------------------------------------
input_column, review_column = st.columns(
    [1, 1.15],
    gap="large",
)

with input_column:
    with st.container(border=True):
        st.subheader("01 · Source code")
        st.caption("Choose how you want to provide your Python code.")

        input_method = st.radio(
            "Input method",
            ["Paste code", "Upload a file"],
            horizontal=True,
            label_visibility="collapsed",
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
                height=360,
                key="code_editor",
                label_visibility="collapsed",
            )

            if len(source_code.encode("utf-8")) > 200_000:
                st.warning("Please keep the code under 200 KB.")
                input_ready = False

        else:
            uploaded_file = st.file_uploader(
                "Upload a Python file",
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
                        "Could not read this file. Save it as UTF-8 "
                        "and upload it again."
                    )
                    input_ready = False

        # Associate results with the exact input and selected model.
        source_hash = hashlib.sha256(
            source_code.encode("utf-8")
        ).hexdigest()

        workspace_identity = (
            input_method,
            file_name,
            source_hash,
            model_name,
            input_ready,
        )

        if (
            st.session_state.workspace_identity
            != workspace_identity
        ):
            st.session_state.workspace_identity = workspace_identity
            st.session_state.syntax_result = None
            st.session_state.ai_review = None
            st.session_state.ai_error = None
            st.session_state.review_seconds = None
            st.session_state.review_timestamp = None

        syntax_button_column, ai_button_column = st.columns(2)

        with syntax_button_column:
            syntax_clicked = st.button(
                "Check syntax",
                disabled=not input_ready,
                use_container_width=True,
            )

        with ai_button_column:
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
            "Syntax checks run locally. AI suggestions need "
            "your review before use."
        )


# --------------------------------------------------
# RUN REQUESTED ACTIONS
# --------------------------------------------------
if syntax_clicked:
    st.session_state.syntax_result = check_syntax(source_code)

if review_clicked:
    st.session_state.ai_review = None
    st.session_state.ai_error = None
    st.session_state.review_seconds = None
    st.session_state.review_timestamp = None

    syntax_result = check_syntax(source_code)
    st.session_state.syntax_result = syntax_result

    if syntax_result["valid"]:
        try:
            started_at = time.perf_counter()

            with review_column:
                with st.spinner("Reviewing your Python code..."):
                    generated_review = review_code(
                        source_code=source_code,
                        api_key=api_key,
                        model=model_name,
                    )

            st.session_state.ai_review = generated_review
            st.session_state.review_seconds = round(
                time.perf_counter() - started_at,
                1,
            )
            st.session_state.review_timestamp = datetime.now(
                timezone.utc
            ).isoformat(timespec="seconds")

        except Exception as error:
            error_details = f"{type(error).__name__}: {error}"

            if api_key:
                error_details = error_details.replace(
                    api_key,
                    "[API KEY HIDDEN]",
                )

            st.session_state.ai_error = error_details


# --------------------------------------------------
# REVIEW PANEL
# --------------------------------------------------
with review_column:
    with st.container(border=True):
        st.subheader("02 · Review results")
        st.caption(
            "AI findings, local syntax checks, and your report "
            "in one place."
        )

        findings_tab, syntax_tab, export_tab = st.tabs(
            ["AI findings", "Syntax check", "Export report"]
        )

        with findings_tab:
            if st.session_state.ai_error:
                st.error("The AI review could not be completed.")

                with st.expander("Error details", expanded=True):
                    st.code(
                        st.session_state.ai_error,
                        language="text",
                    )

            elif st.session_state.ai_review:
                st.success("AI review received")
                st.caption(
                    f"Model requested: {model_name} · "
                    f"Response time: "
                    f"{st.session_state.review_seconds} seconds"
                )

                st.markdown(st.session_state.ai_review)

                st.divider()
                st.caption(
                    "AI-generated findings are not verified defects. "
                    "Review assumptions and test proposed changes."
                )

            elif (
                st.session_state.syntax_result is not None
                and not st.session_state.syntax_result["valid"]
            ):
                st.warning(
                    "Resolve the syntax issue before requesting "
                    "an AI review. Open the Syntax check tab."
                )

            else:
                st.markdown(
                    """
                    <div class="empty-state">
                        <div class="empty-icon">⌘</div>
                        <div class="empty-title">
                            Ready for a fresh perspective?
                        </div>
                        <div class="empty-description">
                            Add your Python code on the left,
                            then select <strong>Review with AI</strong>.
                            Your findings will appear here.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with syntax_tab:
            syntax_result = st.session_state.syntax_result

            if syntax_result is None:
                st.info(
                    "Select Check syntax to inspect your code "
                    "without making an API request."
                )

            elif syntax_result["valid"]:
                st.success(syntax_result["message"])
                st.caption(
                    "Parsing succeeded. This does not verify "
                    "runtime behavior or security."
                )

            else:
                st.error(syntax_result["message"])

                if syntax_result["line"] is not None:
                    st.write(
                        f"**Line:** {syntax_result['line']} · "
                        f"**Column:** {syntax_result['column']}"
                    )

                    lines = source_code.splitlines()
                    error_line = syntax_result["line"]

                    if 1 <= error_line <= len(lines):
                        st.code(
                            lines[error_line - 1],
                            language="python",
                        )

        with export_tab:
            if st.session_state.ai_review:
                report = (
                    "# CodeLens — AI Code Review\n\n"
                    f"- File: {file_name}\n"
                    f"- Model requested: {model_name}\n"
                    f"- Generated at (UTC): "
                    f"{st.session_state.review_timestamp}\n"
                    f"- Response time: "
                    f"{st.session_state.review_seconds} seconds\n\n"
                    "---\n\n"
                    f"{st.session_state.ai_review}\n\n"
                    "---\n\n"
                    "AI-generated suggestions require human review. "
                    "Submitted code was not executed by this app.\n"
                )

                st.write(
                    "Download your review as a Markdown file."
                )

                st.download_button(
                    "Download review (.md)",
                    data=report,
                    file_name="codelens_review.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            else:
                st.info(
                    "Complete an AI review to enable report download."
                )


# --------------------------------------------------
# WORKSPACE SUMMARY
# --------------------------------------------------
st.write("")

line_count = len(source_code.splitlines())
syntax_result = st.session_state.syntax_result

if syntax_result is None:
    syntax_status = "Not checked"
elif syntax_result["valid"]:
    syntax_status = "Passed"
else:
    syntax_status = "Needs attention"

if st.session_state.ai_error:
    review_status = "Failed"
elif st.session_state.ai_review:
    review_status = "Received"
else:
    review_status = "Not requested"

metric_one, metric_two, metric_three = st.columns(3)

metric_one.metric("Source lines", line_count)
metric_two.metric("Syntax check", syntax_status)
metric_three.metric("AI review", review_status)