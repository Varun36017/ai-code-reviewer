import streamlit as st

from reviewer.ai_reviewer import review_code
from reviewer.syntax_checker import check_syntax


# --------------------------------------------------
# PAGE SETTINGS
# --------------------------------------------------
st.set_page_config(
    page_title="AI Code Reviewer",
    page_icon="🔍",
    layout="wide",
)


# --------------------------------------------------
# LOAD THE SAVED API KEY
# --------------------------------------------------
try:
    api_key = st.secrets.get("GEMINI_API_KEY", "")
except FileNotFoundError:
    api_key = ""


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
with st.sidebar:
    st.title("🔍 Code Reviewer")
    st.caption("Your code review and learning workspace")
    st.divider()

    st.subheader("Gemini configuration")

    model_name = st.text_input(
        "Gemini model ID",
        value="gemini-2.5-flash",
    )

    if api_key.strip():
        st.success("API key configured")
        st.caption("Loaded from your private configuration.")
    else:
        st.warning("API key not configured")
        st.caption(
            "Add GEMINI_API_KEY to .streamlit/secrets.toml."
        )

    st.divider()
    st.write("Features: Python syntax checking and AI review")


# --------------------------------------------------
# PAGE INTRODUCTION
# --------------------------------------------------
st.title("Python Code Review Workspace")
st.write(
    "Paste Python code or upload a file to check its syntax "
    "and request an AI-assisted review."
)


# --------------------------------------------------
# CODE INPUT
# --------------------------------------------------
code_column, result_column = st.columns(2, gap="large")

with code_column:
    st.subheader("Your code")

    input_method = st.radio(
        "How would you like to provide your code?",
        ["Paste code", "Upload a file"],
        horizontal=True,
    )

    source_code = ""
    input_ready = True

    if input_method == "Paste code":
        source_code = st.text_area(
            "Python code",
            value='print("Hello, Varun!")',
            height=350,
        )

    else:
        uploaded_file = st.file_uploader(
            "Choose a Python file",
            type=["py"],
        )

        if uploaded_file is None:
            input_ready = False

        elif uploaded_file.size > 200_000:
            st.warning("Please upload a file smaller than 200 KB.")
            input_ready = False

        else:
            try:
                source_code = uploaded_file.getvalue().decode(
                    "utf-8-sig"
                )

                st.caption(f"Selected file: {uploaded_file.name}")
                st.code(source_code, language="python")

            except UnicodeDecodeError:
                st.error(
                    "This file could not be read. "
                    "Save it with UTF-8 encoding and try again."
                )
                input_ready = False

    check_clicked = st.button(
        "Check syntax",
        type="primary",
        disabled=not input_ready,
    )


# --------------------------------------------------
# SYNTAX CHECK RESULT
# --------------------------------------------------
with result_column:
    st.subheader("Check result")

    if check_clicked:
        result = check_syntax(source_code)

        if result["valid"]:
            st.success(result["message"])
            st.caption(
                "Syntax passed. Logic, security, and performance "
                "have not been checked yet."
            )

        else:
            st.error(result["message"])

            if result["line"] is not None:
                st.write(
                    f"Line: {result['line']} | "
                    f"Column: {result['column']}"
                )

    else:
        st.info("Provide your code and click Check syntax.")


# --------------------------------------------------
# AI REVIEW STATE
# --------------------------------------------------
if "ai_review" not in st.session_state:
    st.session_state.ai_review = None

if "ai_error" not in st.session_state:
    st.session_state.ai_error = None

review_context = (
    input_method,
    source_code,
    model_name.strip(),
)

if st.session_state.get("review_context") != review_context:
    st.session_state.review_context = review_context
    st.session_state.ai_review = None
    st.session_state.ai_error = None


# --------------------------------------------------
# AI REVIEW BUTTON
# --------------------------------------------------
st.divider()
st.subheader("AI code review")
st.caption(
    "Clicking Review with AI sends the submitted code "
    "to Google's Gemini API."
)

review_clicked = st.button(
    "Review with AI",
    type="primary",
    disabled=(
        not input_ready
        or not source_code.strip()
        or not api_key.strip()
        or not model_name.strip()
    ),
)

if review_clicked:
    st.session_state.ai_review = None
    st.session_state.ai_error = None

    syntax_result = check_syntax(source_code)

    if not syntax_result["valid"]:
        st.warning(
            "Please fix the syntax error before requesting "
            "an AI review."
        )

    else:
        try:
            with st.spinner("Gemini is reviewing your code..."):
                review = review_code(
                    source_code=source_code,
                    api_key=api_key,
                    model=model_name.strip(),
                )

            st.session_state.ai_review = review

        except Exception as error:
            error_details = f"{type(error).__name__}: {error}"

            # Hide the API key if it appears in the error.
            if api_key:
                error_details = error_details.replace(
                    api_key,
                    "[API KEY HIDDEN]",
                )

            st.session_state.ai_error = error_details


# --------------------------------------------------
# DISPLAY AI REVIEW OR ERROR
# --------------------------------------------------
if st.session_state.ai_error:
    st.error("The AI review could not be completed.")

    with st.expander("Show error details", expanded=True):
        st.code(
            st.session_state.ai_error,
            language="text",
        )

if st.session_state.ai_review:
    st.markdown(st.session_state.ai_review)