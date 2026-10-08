# Patch & Task Compliance Assistant — Phase 1 Scaffold

Minimal working starting point for the compliance-checking phase of the MIP AI Challenge.
Goal of this scaffold: prove the comparison logic is trustworthy before spending time on
UI polish, Jira integration, or server access.

**Runs with zero setup by default** — no API key, no Jira access, no Docker even
required for the Streamlit app. See "Mock mode" below for what that does and doesn't
prove.

## What's here

- **`comparison_engine.py`** — the reusable core. One function, `compare_documents()`,
  used across all four compliance stages. This is the piece most worth getting right;
  everything else is plumbing around it.
- **`app.py`** — a bare Streamlit chat-style shell. Paste documents in, run a check,
  see structured output. One task per session, no persistence yet.
- **`requirements.txt`** — `anthropic` + `streamlit`.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```
That's it — runs immediately in mock mode (see below), no key needed. To get real
AI-judged results instead of placeholders:
```bash
export ANTHROPIC_API_KEY=your_key_here
export USE_MOCK_CLAUDE=false
streamlit run app.py
```

## Mock mode — running the whole build with no API key

`USE_MOCK_CLAUDE=true` is the default everywhere in this project (Streamlit, the MCP
server, Docker). With it on, `compare_documents()` never calls Claude at all — it
returns a clearly-labeled placeholder result instead (`mocked=True` on the result, a
`[MOCK MODE]` prefix in the summary, a warning banner in the Streamlit app).

**What this unblocks:** everyone can build and demo the entire pipeline — Streamlit,
the MCP server's tools, the n8n workflow, the Jira/fixtures plumbing — without anyone
needing an Anthropic API key at all. Good for confirming the parts fit together.

**What this does NOT give you:** an actual compliance judgment. The mock result uses a
crude word-overlap heuristic just so it isn't identical every time — it has no real
understanding of the documents, and can't tell you whether a proposal actually misses
something the notes asked for. **Prompt tuning (Jony, Kamo, Karabo's work) fundamentally
needs a real key** — there's nothing to tune against without one. Set
`USE_MOCK_CLAUDE=false` with a valid `ANTHROPIC_API_KEY` the moment real judgment
quality, not just plumbing, is what's being checked.

## How the prompt templates work

Each of the four stages (`notes_vs_proposal`, `proposal_vs_amended`, `proposal_vs_planning`,
`planning_vs_asd`) has its own prompt template in `PROMPT_TEMPLATES` inside
`comparison_engine.py`. They all ask for the same JSON shape back:

```json
{
  "coverage_gaps": ["..."],
  "deviations": ["..."],
  "confidence": "high|medium|low",
  "summary": "..."
}
```

This is deliberate: keeping one output schema across all stages means the Streamlit UI,
any future dashboard, and any future Jira write-back all stay simple, and a developer
tuning one stage's prompt doesn't need to touch the rendering code.

**This is where most of the team's early effort should go.** The prompts here are a
reasonable starting point, not a finished product — they need testing against real
task data (see below) and will need tightening once you see real false positives/negatives.

## Suggested first week, per person (from the plan doc)

- **Jony** — tune `notes_vs_proposal` against 3-5 real completed tasks. This is stage 1;
  get it reliable before building on it.
- **Kamo** — tune `proposal_vs_planning` (note: this scaffold's `proposal_vs_amended`
  slots in between if you're including the design-session step; confirm with Nathan
  whether that's in scope for the demo or a stretch item).
- **Karabo** — tune `planning_vs_asd`.
- **Niral** — extend `app.py`: task list/session persistence so more than one task can
  be tracked, basic auth if needed, cleaner layout.
- **Tevin** — build the check-in feature as a new module (`checkin.py`) following the
  same pattern: reads planning + prior check-ins, asks the developer what's changed,
  logs the answer. This doesn't call `compare_documents()` — it's more of a structured
  Q&A loop — so it's a good candidate to build as its own thing in parallel.

## Jira integration (`jira_client.py`)

Added ahead of confirmed server access, so it's ready to test the moment a token exists.
Not wired into `app.py` yet — documents are still pasted in manually there.

Plain REST calls via `requests`, no extra platform. Three functions:

- `get_issue(issue_key)` — pulls summary, description, all comments, and attachment metadata
- `download_attachment(attachment, out_dir)` — downloads one attached file to disk
  (turning that file into text is a separate step — reuse whatever document-reading
  approach the rest of the team uses, don't duplicate it here)
- `post_comment(issue_key, body)` — posts a comment back to the issue
- `format_comparison_comment(stage_label, result)` — turns a `ComparisonResult` into a
  readable Jira comment body, kept separate so the comparison engine stays Jira-agnostic

**Config (env vars):**
- `JIRA_BASE_URL` — e.g. `https://jira.yourcompany.com`
- `JIRA_AUTH_MODE` — `"token"` for Server/Data Center (Personal Access Token) or
  `"basic"` for Cloud (email + API token). Confirm which one you're on once Grant responds.
- `JIRA_PAT` — Server/DC personal access token
- `JIRA_EMAIL` / `JIRA_API_TOKEN` — Cloud auth, if applicable

**Test it standalone** once you have a token and a real issue key:
```bash
python3 jira_client.py TASK-1234
```

**Wiring it into `app.py`** once server access is confirmed: swap the "paste text" boxes
for an optional "load from Jira task" input that calls `get_issue()` and feeds its
description/comments/attachment text straight into `compare_documents()`.

## Developing without real Jira access (`fixtures.py`)

Three complete fake Jira tasks (`TASK-1001`, `TASK-1002`, `TASK-1003`), each with a full
lifecycle — notes, proposal, design session, amended proposal, planning comment, and a
completed ASD — so every comparison stage has something realistic to test against right
now, before real Jira/TST access exists.

Deliberately mixed, not all "clean passes":
- **TASK-1001**: proposal initially misses a requirement (checking the web client),
  caught and fixed by the amended proposal — good for testing that gap detection works
  and that a fixed gap doesn't get flagged again downstream
- **TASK-1002**: planning misses covering one test case, and the ASD shows a requirement
  (audit logging) deliberately deferred *with* an explanation — good for testing that
  "explained deviations" get treated differently from unexplained ones
- **TASK-1003**: the ASD silently drops a requirement (the email report) with zero
  explanation anywhere — the clearest test of whether `planning_vs_asd` actually catches
  an unexplained deviation, not just rubber-stamping everything

**Toggle**: `USE_FAKE_JIRA=true` (the default in `docker-compose.yml` right now) makes
`mcp_server.py` read from `fixtures.py` instead of calling the real Jira API. Flip to
`false` once real Jira credentials exist — nothing else in the code needs to change,
`fixtures.py` and `jira_client.py` return the same shape.

A new tool, `list_available_test_issues`, returns the fake issue keys when fixture mode
is on — call this first in the inspector so you know what to test `get_jira_issue`
against.

## MCP server (`mcp_server.py`)

Exposes Jira and the comparison engine as tools Claude can call directly, rather than
Python pre-fetching everything and handing Claude a finished prompt. Same underlying
functions as `jira_client.py` and `comparison_engine.py` — this file just describes
them to Claude in MCP's format.

Four tools:
- `get_jira_issue(issue_key)` — summary, description, comments, attachment list
- `get_jira_attachment_text(issue_key, filename)` — downloads and returns attachment text
  (plain text only for now — swap in real docx/pdf extraction before relying on this
  for actual proposal/ASD documents)
- `run_compliance_check(reference_doc, new_doc, comparison_type, task_context)` — runs
  one of the four comparison stages
- `post_jira_comment(issue_key, comment_body)` — posts a result back to the issue

**Test locally:**
```bash
python3 mcp_server.py
```
Runs on stdio by default — pair with the MCP inspector (`npx @modelcontextprotocol/inspector`)
for interactive testing, or connect it directly in a Claude API call via the `mcp_servers`
parameter once it's running on `streamable-http` (see the commented line at the bottom
of the file).

**Important behavior change to be aware of:** the four comparison stages become tools
Claude can call in whatever order it decides, rather than a fixed sequence Python
controls. That's more flexible, but less predictable — worth deciding deliberately
whether that trade fits a compliance tool, versus keeping the fixed sequence and using
MCP only for the Jira read/write parts.

## Full build: Docker + MCP + webhooks + n8n

`docker compose up --build` now brings up two services together, on a shared network:

- **`mcp-server`** — the MCP server (unchanged), reachable at `http://mcp-server:8000/mcp`
  from other containers, or `http://localhost:8000/mcp` from your host machine
- **`n8n`** — the orchestration layer, reachable at `http://localhost:5678`

The trigger for the whole workflow is a Jira webhook. n8n's Webhook trigger node
generates a URL the moment you add it — no separate webhook-receiving code needed on
our side. That URL is what gets handed to Grant to configure as the Jira webhook target,
once Jira webhook access is confirmed.

**Full build-out spec for the n8n workflow itself is in `N8N_WORKFLOW.md`** — written as
node-by-node steps rather than a one-click import, since exact node availability varies
by n8n version.

**Before pointing a real Jira webhook at it:** `WEBHOOK_URL` in `docker-compose.yml`
needs to be an address Jira can actually reach — `localhost` only works for testing
from the same machine. For local testing before this is hosted somewhere permanent
on MIP infrastructure, a tunnel tool like ngrok can expose your local n8n instance
temporarily.

## Running the MCP server in Docker

Since MIP already runs on Docker, the MCP server can be containerized rather than run
as a bare Python process. Two new files:

- **`Dockerfile`** — builds the MCP server (just `mcp_server.py` + its two dependencies,
  `comparison_engine.py` and `jira_client.py`) into an image
- **`docker-compose.yml`** — runs it, with config passed in as environment variables

**One change this requires:** transport switches from `stdio` (local process-to-process
only, what you'd use for quick testing) to `streamable-http` (reachable over the network
at a URL) — this is the default now via `MCP_TRANSPORT`, since a containerized server needs
to be reachable by n8n, the Claude API, or anything else calling it, not just a process on
the same machine.

**To run it:**
```bash
# create a .env file (not committed) with your real values:
#   ANTHROPIC_API_KEY=...
#   JIRA_BASE_URL=...
#   JIRA_PAT=...   (or JIRA_EMAIL + JIRA_API_TOKEN for Cloud)

docker compose up --build
```
It'll be reachable at `http://localhost:8000/mcp`. Point n8n's MCP client node, or a
Claude API `mcp_servers` entry, at that URL once it's running somewhere network-reachable
(not just localhost, if n8n or Claude needs to reach it from elsewhere).

Not build-tested in this environment (no Docker available here) — worth confirming
`docker compose build` works on your end before relying on it.

## n8n notes

Not build-tested in this environment (no Docker here to run `docker compose up` and
confirm the containers actually talk to each other) — worth a full run-through on your
end before the meeting demo relies on it. The `mcp-server` reachability from inside the
`n8n` container specifically (`http://mcp-server:8000`, not `localhost`) is the detail
most likely to trip up a first attempt.

## What's deliberately NOT in this scaffold
- No database — session state resets on restart. Fine for a POC demo, not for real use.
- No auth on the Streamlit app itself
- No retrieval/RAG — every comparison sends full document text in the prompt, which is
  fine at this document size. Don't add RAG here; that's a Phase 3 / side-project concern
  if documents ever get too large to fit in context.

## Test data note

The prompts above are only as good as what you test them against. Before tuning further,
pull the 5-10 real completed tasks mentioned in the plan doc (notes, proposal, planning
comment, ASD) — this matters more right now than any code change.
