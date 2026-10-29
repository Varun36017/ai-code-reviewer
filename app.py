import streamlit as st

from reviewer.syntax_checker import check_syntax


st.set_page_config(
    page_title="AI Code Reviewer",
    page_icon="🔍",
    layout="wide",
)

with st.sidebar:
    st.title("🔍 Code Reviewer")
    st.caption("Your code review and learning workspace")
    st.divider()
    st.write("Current feature: Python syntax checking")

st.title("Python Code Review Workspace")
st.write("Paste your Python code below to check its syntax.")

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
                source_code = uploaded_file.getvalue().decode("utf-8-sig")

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
        st.info("Paste your code and click Check syntax.")