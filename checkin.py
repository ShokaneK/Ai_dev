"""
Check-in feature for the Patch and Task Compliance Assistant.

Records what changed between the developer's planning comment and the finished ASD,
so the final compliance stage (planning_vs_asd) can tell an explained change from one
that quietly disappeared.

TRIGGER: a Jira status change into Code Review (set CHECKIN_TRIGGER_STATUS if your
workflow names it differently). n8n's Jira webhook hands the event payload to
handle_status_change(), which:
  1. reads the task's [PLANNING] comment and any earlier [CHECK-IN] comments
  2. turns the plan into a short list of planned items (code changes and tests)
  3. posts a [CHECK-IN REQUEST] comment asking the developer, item by item, whether
     each was done as planned, changed, deferred or dropped, and why

The developer answers in one of two ways, both ending as the same tagged comment:
  - replying in Jira with a comment starting [CHECK-IN] (the request includes a
    fill-in template), or
  - through record_checkin() (from Streamlit, an MCP tool, etc.), which formats and
    posts the [CHECK-IN] comment for them.

build_planning_reference() then returns the planning comment plus every check-in,
oldest first, ready to pass as reference_doc to
compare_documents(..., comparison_type="planning_vs_asd").

Storage is Jira itself: check-ins live as tagged comments on the task, so there is no
database to add and the history survives restarts.

Runs with zero setup like the rest of the build: USE_FAKE_JIRA=true reads fixtures.py,
and USE_MOCK_CLAUDE=true swaps the Claude call that splits the plan into items for a
crude sentence split (clearly labeled [MOCK]).
"""

import os
import re
import json
from datetime import datetime, timezone
from typing import Optional

import fixtures
import jira_client
from comparison_engine import MOCK_MODE, MODEL, client

USE_FAKE_JIRA = os.environ.get("USE_FAKE_JIRA", "true").lower() == "true"
jira_source = fixtures if USE_FAKE_JIRA else jira_client

# The Jira status name that triggers a check-in request. Match it to MIP's workflow.
TRIGGER_STATUS = os.environ.get("CHECKIN_TRIGGER_STATUS", "Code Review")

PLANNING_TAG = "[PLANNING]"
CHECKIN_TAG = "[CHECK-IN]"
REQUEST_TAG = "[CHECK-IN REQUEST]"

ITEM_STATUSES = ("done as planned", "changed", "deferred", "dropped")


# ---------------------------------------------------------------------------
# Reading the task's comments
# ---------------------------------------------------------------------------

def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _comments(issue_key: str) -> list:
    """All comment bodies on the issue, oldest first."""
    issue = jira_source.get_issue(issue_key)
    comments = list(issue.comments)
    if USE_FAKE_JIRA:
        # fixtures.post_comment only logs to memory, so merge those "posted"
        # comments back in. That way a local demo shows check-ins building up.
        comments += [
            c["body"] for c in fixtures._fake_posted_comments if c["issue_key"] == issue_key
        ]
    return comments


def _tagged(comments: list, tag: str) -> list:
    # Note: "[CHECK-IN]" does not match "[CHECK-IN REQUEST]", so the tags stay distinct.
    return [c for c in comments if c.strip().startswith(tag)]


def get_planning_comment(issue_key: str) -> Optional[str]:
    """The latest [PLANNING] comment (if the task was re-planned, the newest plan wins)."""
    planning = _tagged(_comments(issue_key), PLANNING_TAG)
    return planning[-1] if planning else None


def get_checkin_history(issue_key: str) -> list:
    """Every [CHECK-IN] comment on the task, oldest first."""
    return _tagged(_comments(issue_key), CHECKIN_TAG)


def has_open_request(issue_key: str) -> bool:
    """
    True if the newest check-in-related comment is a request nobody has answered.
    Stops a task that bounces in and out of Code Review from collecting duplicate
    requests before the developer has replied.
    """
    related = [
        c for c in _comments(issue_key) if c.strip().startswith((CHECKIN_TAG, REQUEST_TAG))
    ]
    return bool(related) and related[-1].strip().startswith(REQUEST_TAG)


# ---------------------------------------------------------------------------
# Turning the plan into a list of items to ask about
# ---------------------------------------------------------------------------

ITEMS_PROMPT = """Below is a developer's planning comment for a software task, followed by any
check-ins already recorded for it. List each distinct planned code change and each planned
test as a short, specific item (under 15 words each), in the order they appear in the plan.
Leave out any item an earlier check-in already reported as deferred or dropped.

Respond with ONLY a JSON object, no other text, no markdown fences:
{{"planned_items": ["...", "..."]}}

--- PLANNING COMMENT ---
{planning}

--- EARLIER CHECK-INS ---
{history}
"""


def _split_items(planning: str, prefix: str = "") -> list:
    """Crude sentence/numbered-list split. Used in mock mode and as a parse fallback."""
    text = planning.replace(PLANNING_TAG, "")
    parts = re.split(r"(?:\(\d+\)|[.;])\s+", text)
    items = [p.strip(" .,:") for p in parts if len(p.strip(" .,:")) > 10]
    return [f"{prefix}{p}" for p in items[:8]]


def extract_planned_items(planning: str, history: list) -> list:
    if MOCK_MODE:
        return _split_items(planning, prefix="[MOCK] ")

    prompt = ITEMS_PROMPT.format(
        planning=planning.strip(),
        history="\n\n".join(history) if history else "(none)",
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    try:
        cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        items = json.loads(cleaned).get("planned_items", [])
        if isinstance(items, list) and items:
            return [str(i) for i in items]
    except (json.JSONDecodeError, AttributeError):
        pass
    # Don't block the check-in over a bad parse: fall back to the crude split.
    return _split_items(planning)


# ---------------------------------------------------------------------------
# Step 1: status change -> post a check-in request
# ---------------------------------------------------------------------------

def format_request(issue_key: str, items: list, has_planning: bool) -> str:
    lines = [f"{REQUEST_TAG} {issue_key} moved to {TRIGGER_STATUS} on {_today()}.", ""]

    if has_planning:
        lines.append(
            "Before review, please confirm what happened to each planned item. Reply with "
            f"a comment that starts with {CHECKIN_TAG}, using the template below. Mark each "
            "item as done as planned, changed, deferred or dropped, and give a reason for "
            "anything that isn't done as planned. List anything you did that wasn't in the "
            "plan under Added."
        )
    else:
        lines.append(
            f"No {PLANNING_TAG} comment was found on this task, so there is no plan to check "
            f"against. Please reply with a comment that starts with {CHECKIN_TAG} describing "
            "what was built and tested, and anything that changed along the way."
        )

    lines += ["", "Template:", CHECKIN_TAG]
    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. {item}: <done as planned / changed / deferred / dropped> - <reason if not done as planned>"
        )
    lines.append("Added: <anything not in the plan, with reason, or 'none'>")
    return "\n".join(lines)


def start_checkin(issue_key: str) -> dict:
    """Post a [CHECK-IN REQUEST] for this task, unless one is already waiting."""
    if has_open_request(issue_key):
        return {
            "action": "skipped",
            "issue_key": issue_key,
            "reason": "an earlier check-in request is still unanswered",
        }

    planning = get_planning_comment(issue_key)
    history = get_checkin_history(issue_key)
    items = extract_planned_items(planning, history) if planning else []

    body = format_request(issue_key, items, has_planning=planning is not None)
    jira_source.post_comment(issue_key, body)
    return {
        "action": "requested",
        "issue_key": issue_key,
        "planned_items": items,
        "comment": body,
    }


def handle_status_change(payload: dict) -> dict:
    """
    Entry point for n8n's Jira webhook. Expects Jira's standard issue_updated payload:
        {"issue": {"key": "TASK-1234"},
         "changelog": {"items": [{"field": "status", "toString": "Code Review", ...}]}}
    Inspect one real payload from MIP's Jira before relying on these field names
    (see N8N_WORKFLOW.md, "Known open items").
    """
    issue_key = (payload.get("issue") or {}).get("key")
    if not issue_key:
        return {"action": "ignored", "reason": "no issue key in payload"}

    changes = (payload.get("changelog") or {}).get("items", [])
    moved_to_trigger = any(
        c.get("field") == "status"
        and (c.get("toString") or "").strip().lower() == TRIGGER_STATUS.lower()
        for c in changes
    )
    if not moved_to_trigger:
        return {
            "action": "ignored",
            "issue_key": issue_key,
            "reason": f"not a status change into '{TRIGGER_STATUS}'",
        }

    return start_checkin(issue_key)


# ---------------------------------------------------------------------------
# Step 2: record the developer's answer (when it doesn't come in as a Jira reply)
# ---------------------------------------------------------------------------

def record_checkin(
    issue_key: str,
    entries: list,
    added: Optional[list] = None,
    developer: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """
    Format and post a [CHECK-IN] comment.

    entries: [{"item": "...", "status": "done as planned|changed|deferred|dropped",
               "reason": "..."}]  (reason required unless status is "done as planned")
    added:   [{"item": "...", "reason": "..."}]  for work done that wasn't in the plan
    """
    for e in entries:
        status = e.get("status", "").strip().lower()
        if status not in ITEM_STATUSES:
            raise ValueError(f"Status for '{e.get('item')}' must be one of {ITEM_STATUSES}.")
        if status != "done as planned" and not (e.get("reason") or "").strip():
            raise ValueError(f"'{e.get('item')}' is marked {status}; a reason is required.")

    header = f"{CHECKIN_TAG} {_today()}, {issue_key}"
    if developer:
        header += f", recorded by {developer}"
    lines = [header]

    for i, e in enumerate(entries, 1):
        line = f"{i}. {e['item']}: {e['status'].strip().lower()}"
        if (e.get("reason") or "").strip():
            line += f" - {e['reason'].strip()}"
        lines.append(line)

    if added:
        lines.append("Added:")
        lines += [f"- {a['item']} - {a.get('reason', '').strip() or 'no reason given'}" for a in added]
    else:
        lines.append("Added: none")

    if notes:
        lines.append(f"Notes: {notes.strip()}")

    body = "\n".join(lines)
    jira_source.post_comment(issue_key, body)
    return body


# ---------------------------------------------------------------------------
# Step 3: hand the history to the final compliance stage
# ---------------------------------------------------------------------------

def build_planning_reference(issue_key: str) -> str:
    """Planning comment + all check-ins, as reference_doc for planning_vs_asd."""
    planning = get_planning_comment(issue_key) or f"(No {PLANNING_TAG} comment found on this task.)"
    history = get_checkin_history(issue_key)
    parts = [planning, "CHECK-IN HISTORY:"] + (history or ["(No check-ins recorded.)"])
    return "\n\n".join(parts)


if __name__ == "__main__":
    # Demo with zero setup (fake Jira + mock Claude). TASK-1003's ASD silently drops
    # the email report; here the developer explains it in a check-in, turning it into
    # an explained deviation for the planning_vs_asd stage.
    from comparison_engine import compare_documents

    sample_payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TASK-1003"},
        "changelog": {"items": [
            {"field": "status", "fromString": "In Progress", "toString": "Code Review"}
        ]},
    }

    print("1. Status change to Code Review:")
    print(json.dumps(handle_status_change(sample_payload), indent=2)[:600], "\n")

    print("2. Same status change again, before the developer replies:")
    print(handle_status_change(sample_payload), "\n")

    print("3. Developer records the check-in:")
    record_checkin(
        "TASK-1003",
        entries=[
            {"item": "Nightly batch job moves closed tasks over 90 days to archive table",
             "status": "done as planned"},
            {"item": "Email summary report to task owner per run", "status": "deferred",
             "reason": "SMTP relay not available on TST; agreed with SA to ship as follow-up task"},
        ],
        developer="Developer",
    )

    print("4. Reference document for planning_vs_asd:")
    reference = build_planning_reference("TASK-1003")
    print(reference, "\n")

    result = compare_documents(
        reference_doc=reference,
        new_doc=fixtures.get_attachment_text("TASK-1003", "TASK-1003_ASD.txt"),
        comparison_type="planning_vs_asd",
        task_context="TASK-1003",
    )
    print("5. planning_vs_asd result:", result.summary)
