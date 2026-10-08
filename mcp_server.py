"""
MCP server exposing Jira (and the compliance comparison engine) as tools
Claude can call directly.

This wraps the same functions already in jira_client.py and comparison_engine.py —
it does not replace them. The Python functions still do the actual work; this file
just describes them to Claude in the format MCP requires, so Claude can decide when
to call get_jira_issue, run_compliance_check, or post_jira_comment on its own,
instead of Python deciding the order in advance.

Run standalone for local testing:
    python3 mcp_server.py

This uses stdio transport by default (simplest for local dev / testing with the
MCP inspector). For n8n or any HTTP-based caller, run with streamable-http instead —
see the __main__ block at the bottom.
"""

import os

from mcp.server.mcpserver import MCPServer

import jira_client
import fixtures
from comparison_engine import compare_documents

# Set USE_FAKE_JIRA=true (in .env) to develop and test against the fixture data
# in fixtures.py instead of a real Jira server. Flip to false (or remove it)
# once real Jira access + credentials exist — no other code changes needed,
# jira_client.py and fixtures.py expose the same shape.
USE_FAKE_JIRA = os.environ.get("USE_FAKE_JIRA", "true").lower() == "true"
jira_source = fixtures if USE_FAKE_JIRA else jira_client

server = MCPServer(
    name="mip-compliance-jira",
    description="Read Jira task content and attachments, run compliance comparisons, "
                 "and post results back as comments.",
)


@server.tool()
def list_available_test_issues() -> dict:
    """
    Lists the fake Jira issue keys available for testing when USE_FAKE_JIRA is on.
    Only meaningful in fixture mode — returns an empty note otherwise.
    """
    if not USE_FAKE_JIRA:
        return {"note": "USE_FAKE_JIRA is off — this server is using real Jira, not fixtures."}
    return {"available_issue_keys": list(fixtures._FAKE_ISSUES.keys())}


@server.tool()
def get_jira_issue(issue_key: str) -> dict:
    """
    Fetch a Jira issue's summary, description, comments, and attachment list.

    issue_key: the Jira task key, e.g. "TASK-1234"
    """
    issue = jira_source.get_issue(issue_key)
    return {
        "key": issue.key,
        "summary": issue.summary,
        "description": issue.description,
        "comments": issue.comments,
        "attachments": [
            {"filename": a.filename, "mime_type": a.mime_type}
            for a in issue.attachments
        ],
    }


@server.tool()
def get_jira_attachment_text(issue_key: str, filename: str) -> str:
    """
    Download one attachment from an issue and return its extracted text.

    issue_key: the Jira task key, e.g. "TASK-1234"
    filename: the attachment's filename, as returned by get_jira_issue
    """
    if USE_FAKE_JIRA:
        return fixtures.get_attachment_text(issue_key, filename)

    issue = jira_client.get_issue(issue_key)
    match = next((a for a in issue.attachments if a.filename == filename), None)
    if not match:
        return f"Attachment '{filename}' not found on {issue_key}."

    local_path = jira_client.download_attachment(match, out_dir="/tmp")

    # NOTE: this is a placeholder text extraction step. Swap in the same
    # docx/pdf reading approach the rest of the team is using rather than
    # duplicating it here — this just handles plain text for now.
    try:
        with open(local_path, "r", errors="ignore") as f:
            return f.read()
    except UnicodeDecodeError:
        return (f"Downloaded '{filename}' to {local_path}, but it isn't plain text "
                f"(likely .docx/.pdf) — needs the docx/pdf text extraction step wired in here.")


@server.tool()
def run_compliance_check(
    reference_doc: str,
    new_doc: str,
    comparison_type: str,
    task_context: str = "",
) -> dict:
    """
    Run one compliance comparison stage using the existing comparison engine.

    comparison_type must be one of:
    "notes_vs_proposal", "proposal_vs_amended", "proposal_vs_planning", "planning_vs_asd"
    """
    result = compare_documents(
        reference_doc=reference_doc,
        new_doc=new_doc,
        comparison_type=comparison_type,
        task_context=task_context or None,
    )
    return {
        "coverage_gaps": result.coverage_gaps,
        "deviations": result.deviations,
        "confidence": result.confidence,
        "summary": result.summary,
        "parse_error": result.parse_error,
        "mocked": result.mocked,
    }


@server.tool()
def post_jira_comment(issue_key: str, comment_body: str) -> str:
    """
    Post a comment to a Jira issue — e.g. the output of run_compliance_check,
    formatted as readable text.

    issue_key: the Jira task key, e.g. "TASK-1234"
    comment_body: the comment text to post
    """
    jira_source.post_comment(issue_key, comment_body)
    return f"Comment posted to {issue_key}."


if __name__ == "__main__":
    # MCP_TRANSPORT=stdio for local testing (pair with the MCP inspector or a local client).
    # MCP_TRANSPORT=streamable-http (the default here) for running in Docker / anything
    # that needs to reach this server over the network — n8n, the Claude API's
    # mcp_servers parameter, etc.
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    if transport == "streamable-http":
        # host 0.0.0.0 so the container's port mapping actually reaches this process
        server.run(transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("MCP_PORT", "8000")))
    else:
        server.run(transport=transport)
