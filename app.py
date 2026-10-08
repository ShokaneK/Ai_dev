"""
Patch and Task Compliance Assistant — Phase 1 POC shell.

A thin Streamlit chat interface over the comparison engine. Deliberately basic:
one task per session, paste-in text boxes for each document stage, no Jira/server
integration yet. The goal is to prove the comparison logic is trustworthy before
spending any time on UI polish or live integrations.

Run with: streamlit run app.py
"""

import streamlit as st
from comparison_engine import compare_documents, MOCK_MODE

st.set_page_config(page_title="Patch & Task Compliance Assistant", layout="wide")

if MOCK_MODE:
    st.warning(
        "🧪 **Mock mode is ON** — no Anthropic API key is being used, and results below "
        "are placeholders, not real AI judgments. Good for testing that the app itself "
        "works; not for judging whether the compliance logic is any good. Set "
        "`USE_MOCK_CLAUDE=false` with a valid `ANTHROPIC_API_KEY` for real results."
    )

STAGES = [
    ("notes_vs_proposal", "1. Initial Notes vs Proposal"),
    ("proposal_vs_amended", "2. Proposal vs Amended Proposal (post design session)"),
    ("proposal_vs_planning", "3. Proposal vs Planning Comment"),
    ("planning_vs_asd", "4. Planning vs ASD"),
]

if "task_context" not in st.session_state:
    st.session_state.task_context = ""
if "results" not in st.session_state:
    st.session_state.results = {}  # comparison_type -> ComparisonResult
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []  # list of (role, text) for the running conversation


def log(role: str, text: str):
    st.session_state.chat_log.append((role, text))


st.title("Patch & Task Compliance Assistant")
st.caption("Phase 1 POC — compliance checking only. No Jira or server integration yet.")

st.session_state.task_context = st.text_input(
    "Task number / reference (optional, used for grounding only)",
    value=st.session_state.task_context,
)

st.divider()

for comparison_type, label in STAGES:
    with st.expander(label, expanded=(comparison_type not in st.session_state.results)):
        col1, col2 = st.columns(2)
        with col1:
            reference_doc = st.text_area(
                "Reference document (earlier stage)",
                key=f"ref_{comparison_type}",
                height=200,
            )
        with col2:
            new_doc = st.text_area(
                "Document to check (later stage)",
                key=f"new_{comparison_type}",
                height=200,
            )

        if st.button(f"Run check — {label}", key=f"btn_{comparison_type}"):
            if not reference_doc.strip() or not new_doc.strip():
                st.warning("Paste both documents before running the check.")
            else:
                with st.spinner("Comparing..."):
                    result = compare_documents(
                        reference_doc=reference_doc,
                        new_doc=new_doc,
                        comparison_type=comparison_type,
                        task_context=st.session_state.task_context,
                    )
                st.session_state.results[comparison_type] = result
                log("assistant", f"Ran {label} — confidence: {result.confidence}")

        result = st.session_state.results.get(comparison_type)
        if result:
            if result.parse_error:
                st.error("Model response could not be parsed as JSON. Raw output below.")
                st.code(result.raw_response)
            else:
                if result.mocked:
                    st.caption("🧪 Mocked result — not a real AI judgment.")
                st.markdown(f"**Summary:** {result.summary}")
                st.markdown(f"**Confidence:** {result.confidence}")

                if result.coverage_gaps:
                    st.markdown("**Coverage gaps:**")
                    for gap in result.coverage_gaps:
                        st.markdown(f"- {gap}")
                else:
                    st.markdown("**Coverage gaps:** none flagged")

                if result.deviations:
                    st.markdown("**Deviations:**")
                    for dev in result.deviations:
                        st.markdown(f"- {dev}")
                else:
                    st.markdown("**Deviations:** none flagged")

st.divider()
st.subheader("Session log")
for role, text in st.session_state.chat_log:
    st.markdown(f"**{role}:** {text}")
