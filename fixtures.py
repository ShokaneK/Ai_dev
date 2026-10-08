"""
Fake Jira data for development and testing before real Jira/TST server access exists.

Three realistic fake tasks, each with a full lifecycle: initial notes, proposal,
design session notes, amended proposal, planning comment, and a completed ASD
(as an attachment). Deliberately mixed — some clean passes, some with real gaps
or deviations — so each comparison stage has both a "good" and a "should be
flagged" example to test against, not just happy-path data.

Comments are tagged with a prefix ([PROPOSAL], [DESIGN SESSION], [AMENDED PROPOSAL],
[PLANNING]) — this is the convention noted as an open item in N8N_WORKFLOW.md for
telling comment types apart. Confirm with the team whether this is the actual
convention to use once real Jira data is seen, this is a reasonable placeholder.

Mirrors jira_client.py's function signatures (get_issue, post_comment) so code
written against fixtures now can swap to the real client later by changing one
import line — see USE_FAKE_JIRA in mcp_server.py.
"""

from jira_client import JiraIssue, JiraAttachment

# ---------------------------------------------------------------------------
# TASK-1001 — Invoice reprint bug (credit notes)
# Clean, mostly-compliant example across all stages. Good "passing" case.
# One deliberate gap: the initial proposal misses the "check web client too"
# ask from the notes — caught and fixed at the design-session/amended stage.
# ---------------------------------------------------------------------------

TASK_1001 = JiraIssue(
    key="TASK-1001",
    summary="Invoice reprint fails for credit notes with partial payment",
    description=(
        "Client reported that the invoice reprint function (prog/invreprint.p) is "
        "failing for credit notes specifically, throwing an error when the original "
        "invoice has been partially paid. Need this fixed and the fix should not "
        "affect normal invoice reprints. Also check if this happens on both the "
        "desktop and web client."
    ),
    comments=[
        "[PROPOSAL] Modify invreprint.p to add a check for credit note type before "
        "applying the partial-payment balance calculation, since that calculation "
        "doesn't apply to credit notes. Will add a conditional branch in the "
        "CalculateBalance procedure. Testing will cover credit note reprint with "
        "partial payment and standard invoice reprint (regression) on desktop.",

        "[DESIGN SESSION] Approach agreed. One addition: please explicitly verify "
        "the web client behaves the same way before closing this out, the notes "
        "specifically asked for both clients to be checked.",

        "[AMENDED PROPOSAL] Updated: same fix as above, and added a web client "
        "test case for the credit note reprint scenario, in addition to desktop "
        "and the standard invoice regression test.",

        "[PLANNING] Will modify CalculateBalance in invreprint.p per the amended "
        "proposal. Test plan: (1) credit note reprint with partial payment, desktop, "
        "(2) same scenario, web client, (3) standard invoice reprint regression, "
        "desktop and web.",
    ],
    attachments=[
        JiraAttachment(
            filename="TASK-1001_ASD.txt",
            content_url="fixture://TASK-1001/TASK-1001_ASD.txt",
            mime_type="text/plain",
        )
    ],
)

TASK_1001_ASD_TEXT = (
    "ASD — TASK-1001\n\n"
    "Changes made: added credit-note-type check in CalculateBalance procedure in "
    "invreprint.p, bypassing the partial-payment balance logic for credit notes.\n\n"
    "Testing performed:\n"
    "- Credit note reprint with partial payment, desktop client: pass\n"
    "- Credit note reprint with partial payment, web client: pass\n"
    "- Standard invoice reprint regression, desktop: pass\n"
    "- Standard invoice reprint regression, web: pass\n\n"
    "No deviations from planning."
)


# ---------------------------------------------------------------------------
# TASK-1002 — Order entry negative quantity validation
# A subtler case: proposal changes shape after design review (moved from UI
# layer to trigger layer), and one requirement (audit logging) gets quietly
# deferred rather than dropped — a good example of an EXPLAINED deviation.
# ---------------------------------------------------------------------------

TASK_1002 = JiraIssue(
    key="TASK-1002",
    summary="Add negative quantity validation to order entry",
    description=(
        "Client wants a validation added to the order entry screen so that "
        "negative quantities are rejected before save. Needs a clear error "
        "message shown to the user, and the rejection should be logged for "
        "audit purposes."
    ),
    comments=[
        "[PROPOSAL] Add a check in the OrderEntry save trigger that rejects any "
        "line with quantity <= 0, returns a clear error message, and logs the "
        "rejection for audit purposes.",

        "[DESIGN SESSION] Since order lines can also be created from the multi-quote "
        "and web ordering flows, suggest implementing this at the OrderLine "
        "before-save trigger level instead of the OrderEntry screen specifically, "
        "so all entry points are covered consistently.",

        "[AMENDED PROPOSAL] Updated to implement the validation in the OrderLine "
        "before-save trigger rather than the OrderEntry screen, covering all entry "
        "points. Still rejects quantity <= 0, shows an error message, and logs for "
        "audit.",

        "[PLANNING] Implement validation in the OrderLine before-save trigger. Test "
        "plan: negative quantity rejected, zero quantity rejected, positive quantity "
        "accepted — covering order entry, multi-quote, and web ordering flows.",
    ],
    attachments=[
        JiraAttachment(
            filename="TASK-1002_ASD.txt",
            content_url="fixture://TASK-1002/TASK-1002_ASD.txt",
            mime_type="text/plain",
        )
    ],
)

TASK_1002_ASD_TEXT = (
    "ASD — TASK-1002\n\n"
    "Changes made: added quantity validation in the OrderLine before-save trigger, "
    "covering order entry, multi-quote, and web ordering flows. Rejects "
    "quantity <= 0 with a clear error message.\n\n"
    "Testing performed:\n"
    "- Negative quantity rejected across all three entry points: pass\n"
    "- Zero quantity rejected across all three entry points: pass\n"
    "- Positive quantity accepted: pass\n\n"
    "Note: audit logging of rejected attempts was deferred — team agreed in "
    "check-in on [date] that this needs a shared audit log table that doesn't "
    "exist yet, tracked as a separate follow-up task rather than blocking this fix."
)


# ---------------------------------------------------------------------------
# TASK-1003 — Archive job for closed tasks
# Planning fully matches the proposal, but the ASD silently drops one
# requirement (the email summary report) with no explanation anywhere.
# Good example of an UNEXPLAINED deviation.
# ---------------------------------------------------------------------------

TASK_1003 = JiraIssue(
    key="TASK-1003",
    summary="Add scheduled archive job for closed tasks older than 90 days",
    description=(
        "Need a scheduled batch job that archives closed tasks older than 90 days. "
        "Must not delete data, only move it to an archive table. Also needs to "
        "email a summary report to the task owner each time it runs."
    ),
    comments=[
        "[PROPOSAL] Build a nightly batch job that selects closed tasks older than "
        "90 days, moves them (not deletes) to a new archive table, and emails a "
        "summary report (count archived, task numbers) to the task owner after "
        "each run.",

        "[DESIGN SESSION] Approach approved as proposed, no changes.",

        "[PLANNING] Implement nightly batch job: select closed tasks > 90 days, "
        "move to archive table, generate and email summary report to task owner "
        "per run. Test plan: verify archived rows removed from live table and "
        "present in archive table, verify email sent with correct count.",
    ],
    attachments=[
        JiraAttachment(
            filename="TASK-1003_ASD.txt",
            content_url="fixture://TASK-1003/TASK-1003_ASD.txt",
            mime_type="text/plain",
        )
    ],
)

TASK_1003_ASD_TEXT = (
    "ASD — TASK-1003\n\n"
    "Changes made: nightly batch job added, selects closed tasks older than 90 "
    "days and moves them to the new archive table.\n\n"
    "Testing performed:\n"
    "- Archived rows correctly removed from live table: pass\n"
    "- Archived rows correctly present in archive table: pass\n\n"
    "No other notes."
    # Deliberately no mention of the email summary report anywhere — this is
    # the unexplained deviation this fixture is designed to test detection of.
)


# ---------------------------------------------------------------------------
# Lookup tables + functions mirroring jira_client.py's interface
# ---------------------------------------------------------------------------

_FAKE_ISSUES = {
    "TASK-1001": TASK_1001,
    "TASK-1002": TASK_1002,
    "TASK-1003": TASK_1003,
}

_FAKE_ATTACHMENT_TEXT = {
    ("TASK-1001", "TASK-1001_ASD.txt"): TASK_1001_ASD_TEXT,
    ("TASK-1002", "TASK-1002_ASD.txt"): TASK_1002_ASD_TEXT,
    ("TASK-1003", "TASK-1003_ASD.txt"): TASK_1003_ASD_TEXT,
}

_fake_posted_comments = []  # in-memory log of "posted" comments, for inspection while testing


def get_issue(issue_key: str) -> JiraIssue:
    """Same signature as jira_client.get_issue, returns fixture data instead of a real call."""
    if issue_key not in _FAKE_ISSUES:
        raise ValueError(
            f"No fake issue '{issue_key}'. Available: {list(_FAKE_ISSUES.keys())}"
        )
    return _FAKE_ISSUES[issue_key]


def get_attachment_text(issue_key: str, filename: str) -> str:
    """
    Fixture equivalent of downloading + reading an attachment. Since fixture
    ASDs are already plain text, this skips the download step entirely.
    """
    key = (issue_key, filename)
    if key not in _FAKE_ATTACHMENT_TEXT:
        return f"No fake attachment text found for {issue_key}/{filename}."
    return _FAKE_ATTACHMENT_TEXT[key]


def post_comment(issue_key: str, body: str) -> dict:
    """
    Fixture equivalent of posting a comment — doesn't call anything real,
    just logs it in memory so you can confirm what would have been posted.
    """
    entry = {"issue_key": issue_key, "body": body}
    _fake_posted_comments.append(entry)
    print(f"[FAKE JIRA] Would post to {issue_key}:\n{body}\n")
    return {"status": "fake_posted", **entry}


if __name__ == "__main__":
    for key in _FAKE_ISSUES:
        issue = get_issue(key)
        print(f"{issue.key} — {issue.summary}")
        print(f"  {len(issue.comments)} comments, {len(issue.attachments)} attachment(s)")
