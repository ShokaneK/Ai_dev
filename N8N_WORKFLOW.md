# n8n Workflow — Compliance Check Automation

What to build inside n8n, once `docker compose up` has it and the MCP server running.
Written as a spec rather than a one-click import, since n8n's exact node versions vary
by install — build these nodes directly in the n8n editor so it's easy to verify and
adjust as you go, rather than debugging a JSON import that assumes a different version.

## The flow, end to end

```
Jira event (status change / comment / attachment)
        |
        v
n8n Webhook trigger  ---- generates a URL the moment you add this node
        |
        v
Function/Set node  ------ extract issue key + figure out which comparison stage
        |                 this event maps to
        v
MCP Client node  -------- call get_jira_issue on the MCP server
        |
        v
Function node  ---------- pull out the right reference/new doc text from the
        |                 issue's description/comments/attachments
        v
MCP Client node  -------- call run_compliance_check
        |
        v
MCP Client node  -------- call post_jira_comment with the formatted result
```

## Node-by-node

**1. Webhook (trigger node)**
- Method: POST
- Path: something memorable, e.g. `/jira-compliance-check`
- Once added, n8n shows you the full URL (e.g. `http://your-n8n-host/webhook/jira-compliance-check`)
  — this is what gets handed to Grant to configure as the Jira webhook target.
- Jira will POST a JSON payload describing the event (issue key, event type, changed
  fields). The exact shape depends on how the webhook is configured on Jira's side —
  inspect one real payload once webhooks are set up, before building the next node,
  rather than guessing the field names.

**2. Function/Set node — map event to comparison stage**
- Reads the incoming webhook payload
- Decides which of the four comparison_type values applies, based on the event
  (e.g. issue moved to "Proposal Submitted" → `notes_vs_proposal`; issue moved to
  "Planning Submitted" → `proposal_vs_planning`, etc.)
- Outputs: `issue_key`, `comparison_type`

**3. MCP Client node — get_jira_issue**
- If your n8n version has a native MCP Client node, point it at
  `http://mcp-server:8000/mcp` (container-to-container, not localhost) and call the
  `get_jira_issue` tool with `issue_key` from step 2.
- If your n8n version doesn't have a native MCP node yet, use an HTTP Request node
  instead, calling the MCP server's endpoint directly — this is a fallback, worth
  checking node availability first since it's a cleaner fit.

**4. Function node — select the right documents**
- The comparison needs a "reference" doc and a "new" doc — which fields of the issue
  those come from depends on `comparison_type` (e.g. for `notes_vs_proposal`, reference
  = issue description, new = latest comment matching "proposal"). This mapping needs
  defining with the team once real issue data/conventions are confirmed — don't guess
  at comment formats without seeing real examples.

**5. MCP Client node — run_compliance_check**
- Calls the `run_compliance_check` tool with `reference_doc`, `new_doc`,
  `comparison_type`, and `task_context` (the issue key)
- Returns `coverage_gaps`, `deviations`, `confidence`, `summary`

**6. MCP Client node — post_jira_comment**
- Formats the result (reuse `format_comparison_comment` logic from `jira_client.py`
  as the template) and calls `post_jira_comment` with `issue_key` + the formatted text

## What to test before wiring to the real webhook

1. Add the Webhook node, get its URL, and send it a fake payload manually (n8n's
   "Test URL" / a tool like curl or Postman) to confirm the flow runs end to end
   before Jira is sending anything real
2. Confirm `mcp-server` is reachable from the n8n container specifically —
   `http://mcp-server:8000/mcp`, not `http://localhost:8000/mcp` (that only
   works from the host machine, not from inside the n8n container)
3. Only after both of those work, hand the real webhook URL to Grant

## Known open items

- Exact Jira webhook payload shape — depends on Jira's webhook config, not something
  to assume in advance
- How comments are formatted/tagged so step 4 can reliably tell a "proposal" comment
  from a "planning" comment — worth agreeing a simple convention with the team
  (e.g. a comment prefix like `[PROPOSAL]`) rather than trying to infer it
- Whether `WEBHOOK_URL` in docker-compose needs to be a real public/internal address
  for Jira to reach, versus a tunnel tool (ngrok, etc.) for local testing before
  MIP hosts this somewhere permanent
