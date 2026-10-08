"""
Jira REST client for the Patch and Task Compliance Assistant.

Plain REST calls, no SDK, no extra platform — same pattern as the Claude API calls
in comparison_engine.py. Works against Jira Server/Data Center and Jira Cloud;
which one you're on changes only the auth method (see below), not the endpoints
used here (the v2 REST API is shared).

Not wired into app.py yet on purpose — Jira TST server access is still pending.
Everything here can be tested standalone once a token exists.
"""

import os
import base64
import mimetypes
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests
except ImportError:
    # Only needed for real Jira calls. Fake-Jira mode (fixtures.py) imports this file
    # for its data classes, so a missing requests package must not stop it loading.
    requests = None

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "")  # e.g. https://jira.yourcompany.com
JIRA_AUTH_MODE = os.environ.get("JIRA_AUTH_MODE", "token")  # "token" (Server/DC PAT) or "basic" (Cloud email+token)

# Server/Data Center: Personal Access Token, sent as a bearer token
JIRA_PAT = os.environ.get("JIRA_PAT", "")

# Cloud: email + API token, sent as HTTP basic auth
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")


def _auth_headers() -> dict:
    if JIRA_AUTH_MODE == "basic":
        creds = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
        return {"Authorization": f"Basic {creds}"}
    return {"Authorization": f"Bearer {JIRA_PAT}"}


def _require_requests():
    if requests is None:
        raise RuntimeError(
            "The 'requests' package is needed for real Jira calls. Install it, or set "
            "USE_FAKE_JIRA=true to use the fake tasks in fixtures.py."
        )


def _get(url: str, **kwargs) -> "requests.Response":
    _require_requests()
    resp = requests.get(url, headers=_auth_headers(), timeout=30, **kwargs)
    resp.raise_for_status()
    return resp


@dataclass
class JiraAttachment:
    filename: str
    content_url: str
    mime_type: str


@dataclass
class JiraIssue:
    key: str
    summary: str
    description: str
    comments: list = field(default_factory=list)   # list of comment body strings, oldest first
    attachments: list = field(default_factory=list)  # list of JiraAttachment


def get_issue(issue_key: str) -> JiraIssue:
    """
    Fetch an issue's summary, description, comments, and attachment metadata.

    issue_key: e.g. "TASK-1234"
    """
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}"
    data = _get(url).json()
    fields = data.get("fields", {})

    comments = [
        c.get("body", "")
        for c in fields.get("comment", {}).get("comments", [])
    ]

    attachments = [
        JiraAttachment(
            filename=a.get("filename", "unnamed"),
            content_url=a.get("content", ""),
            mime_type=a.get("mimeType", "application/octet-stream"),
        )
        for a in fields.get("attachment", [])
    ]

    return JiraIssue(
        key=data.get("key", issue_key),
        summary=fields.get("summary", ""),
        description=fields.get("description", "") or "",
        comments=comments,
        attachments=attachments,
    )


def download_attachment(attachment: JiraAttachment, out_dir: str = ".") -> str:
    """
    Download one attachment to disk. Returns the local file path.

    Note: this just gets the raw bytes onto disk. Turning a .docx/.pdf into text
    is a separate step, reuse whatever document-reading approach the rest of the
    team is already using (e.g. the docx/pdf skills), don't duplicate that here.
    """
    resp = _get(attachment.content_url)
    safe_name = attachment.filename.replace("/", "_")
    out_path = os.path.join(out_dir, safe_name)
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return out_path


def post_comment(issue_key: str, body: str) -> dict:
    """
    Post a comment to an issue, e.g. the summary/gaps/deviations from a
    ComparisonResult formatted as plain text.
    """
    _require_requests()
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/comment"
    resp = requests.post(
        url,
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"body": body},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def format_comparison_comment(stage_label: str, result) -> str:
    """
    Turn a ComparisonResult (from comparison_engine.py) into a readable Jira
    comment body. Kept separate from ComparisonResult itself so the engine
    doesn't need to know anything about Jira formatting.
    """
    lines = [f"*Compliance check: {stage_label}*", "", result.summary, ""]

    lines.append("*Coverage gaps:*")
    lines.extend(f"- {g}" for g in result.coverage_gaps) if result.coverage_gaps else lines.append("None flagged.")

    lines.append("")
    lines.append("*Deviations:*")
    lines.extend(f"- {d}" for d in result.deviations) if result.deviations else lines.append("None flagged.")

    lines.append("")
    lines.append(f"_Confidence: {result.confidence}_")
    return "\n".join(lines)


if __name__ == "__main__":
    # Manual smoke test — needs JIRA_BASE_URL and either JIRA_PAT or
    # JIRA_EMAIL/JIRA_API_TOKEN set, plus a real issue key to test against.
    import sys
    if len(sys.argv) < 2:
        print("Usage: python jira_client.py TASK-1234")
        sys.exit(1)

    issue = get_issue(sys.argv[1])
    print(f"Issue: {issue.key} — {issue.summary}")
    print(f"Description: {issue.description[:200]}...")
    print(f"Comments: {len(issue.comments)}")
    print(f"Attachments: {[a.filename for a in issue.attachments]}")
