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

    source_code = st.text_area(
        "Python code",
        value='print("Hello, Varun!")',
        height=350,
    )

    check_clicked = st.button("Check syntax", type="primary")

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