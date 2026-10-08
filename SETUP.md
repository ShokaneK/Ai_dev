# Setup Guide — Patch & Task Compliance Assistant

Covers what to install, how to run the project on both Mac and Windows, and who's
building what. Written so anyone on the team can follow it, not just whoever set it
up first.

## What you need installed, before anything else

| Requirement | Why | Everyone needs it? |
|---|---|---|
| **Docker Desktop** | Runs the MCP server + n8n containers | Only if running the full stack (see "Who needs what" below) |
| **Python 3.9+** | Runs `comparison_engine.py`, `app.py` directly (without Docker) | Only if working outside Docker |
| **An Anthropic API key** | Lets the code make a *real* Claude judgment instead of a placeholder | Not required to run anything — everything defaults to mock mode. Needed only once real judgment quality (not just plumbing) is what's being tested — see "Mock mode" below |
| **Node.js** | Only for the MCP inspector testing tool | Optional |
| A web browser | To reach n8n (`localhost:5678`) or Streamlit (`localhost:8501`) | If using either |

## Mock mode — the whole build runs with no API key by default

Every part of this project (`comparison_engine.py`, Streamlit, the MCP server, Docker)
defaults to `USE_MOCK_CLAUDE=true`, which skips calling Claude entirely and returns a
clearly-labeled placeholder result instead. This means anyone can install, run, and
demo the *entire pipeline* — Streamlit, the MCP server's tools, the n8n workflow, the
Jira/fixtures plumbing — with zero API key.

**What this does NOT cover:** whether the AI's judgment is actually any good. A mock
result doesn't read the documents with any real understanding — it can't tell you
whether a proposal misses something the notes asked for. That's genuinely the one
thing that needs a real key: **anyone doing prompt tuning (Jony, Kamo, Karabo) needs
`USE_MOCK_CLAUDE=false` plus a real `ANTHROPIC_API_KEY`** — there's nothing to tune
against with mock results. Everyone else (Niral, Tevin, Nathan wiring the pipeline
together) can build and test everything without one.

**Anthropic API key**: get one at console.anthropic.com (API Keys → Create Key), or use
the one provisioned through the company's Anthropic access once that's confirmed. This
is separate from a claude.ai login — a claude.ai seat does not include API access.

## Who actually needs the full Docker + n8n setup

Not everyone. Most of the team can work with just Python and the relevant files:

- **Jony, Kamo, Karabo** (prompt tuning) — don't need Docker. Real tuning work needs
  Python + the `anthropic` package + a real API key with `USE_MOCK_CLAUDE=false` (mock
  mode has nothing for them to tune against). Can also test prompts manually in claude.ai
  chat with no setup at all.
- **Niral** (Streamlit interface) — needs `app.py`, `comparison_engine.py`,
  `requirements.txt`, Python. No API key or Docker required — runs in mock mode by default.
- **Tevin** (check-in feature) — just needs Python and the existing files as reference
- **Nathan** — needs the full stack (Docker, MCP server, n8n) since that's the
  integration layer. No API key required either, unless testing real judgment quality.

If in doubt, start with the plain Python setup below — it's simpler, and the Docker/n8n
setup is only needed once someone is testing the MCP server or the n8n workflow
specifically.

---

## Option A — Plain Python (no Docker), for prompt tuning / Streamlit work

### Mac

1. Open Terminal. Check Python: `python3 --version` (need 3.9+). If missing:
   `brew install python`, or download from python.org.
2. Put the files in a folder, e.g. `~/compliance_assistant`, then `cd` into it.
3. Create a virtual environment: `python3 -m venv venv` then `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run it — works immediately, no key needed (mock mode is on by default):
   - `python3 comparison_engine.py` — quick smoke test
   - `streamlit run app.py` — the chat interface
6. **For real AI judgment instead of placeholders** (needed for actual prompt tuning):
   `export ANTHROPIC_API_KEY=your_key_here` and `export USE_MOCK_CLAUDE=false`, then
   run the same commands again.

### Windows

1. Open PowerShell. Check Python: `python --version` (need 3.9+). If missing, install
   from python.org — during install, tick **"Add python.exe to PATH"**.
2. Put the files in a folder, e.g. `C:\compliance_assistant`, then `cd` into it.
3. Create a virtual environment: `python -m venv venv` then `.\venv\Scripts\activate`
   (if PowerShell blocks this with an execution policy error, run
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again)
4. Install dependencies: `pip install -r requirements.txt`
5. Run it — works immediately, no key needed (mock mode is on by default):
   - `python comparison_engine.py` — quick smoke test
   - `streamlit run app.py` — the chat interface
6. **For real AI judgment instead of placeholders** (needed for actual prompt tuning):
   `$env:ANTHROPIC_API_KEY="your_key_here"` and `$env:USE_MOCK_CLAUDE="false"`, then
   run the same commands again.

---

## Option B — Full stack: Docker + MCP server + n8n

### Mac

1. Install Docker Desktop from docker.com/products/docker-desktop (pick Apple Silicon
   or Intel, check via Apple menu → About This Mac). Open it, wait for the whale icon
   in the menu bar to settle. Confirm: `docker --version` and `docker compose version`.
2. Put all files in one folder, e.g. `~/compliance_assistant`, `cd` into it.
3. Create a `.env` file in that folder — this works as-is, no real key needed:
   ```
   ANTHROPIC_API_KEY=
   USE_MOCK_CLAUDE=true
   JIRA_BASE_URL=
   JIRA_AUTH_MODE=token
   JIRA_PAT=
   USE_FAKE_JIRA=true
   ```
   (`USE_MOCK_CLAUDE=true` skips calling Claude and returns placeholder results — good
   for testing the pipeline. `USE_FAKE_JIRA=true` reads from `fixtures.py` instead of
   real Jira. Flip either to `false` — with a real key / real Jira credentials
   respectively — once testing actual judgment quality or real task data.)
4. Run `docker compose up --build`. First run takes a few minutes.
5. Open `http://localhost:5678` for n8n, or `http://localhost:8000/mcp` is the MCP
   server endpoint (not a normal webpage — used by n8n/inspector, not browsed directly).
6. To stop: Ctrl+C in that terminal, or `docker compose down` from a new tab.

### Windows

1. Install Docker Desktop from docker.com/products/docker-desktop (Windows version).
   **Docker Desktop on Windows requires WSL2** — the installer will prompt you to enable
   this if it isn't already; follow its prompts (may require a restart). Open Docker
   Desktop afterward and wait for it to say "Running."
2. Confirm in PowerShell: `docker --version` and `docker compose version`
3. Put all files in one folder, e.g. `C:\compliance_assistant`, `cd` into it.
4. Create a `.env` file in that folder (Notepad is fine — save as "All Files", not
   `.txt`, so it's actually named `.env`) — this works as-is, no real key needed:
   ```
   ANTHROPIC_API_KEY=
   USE_MOCK_CLAUDE=true
   JIRA_BASE_URL=
   JIRA_AUTH_MODE=token
   JIRA_PAT=
   USE_FAKE_JIRA=true
   ```
5. Run `docker compose up --build` from PowerShell in that folder. First run takes a
   few minutes.
6. Open `http://localhost:5678` for n8n, same as Mac.
7. To stop: Ctrl+C in that terminal, or `docker compose down`.

### Testing with the MCP inspector (optional, either OS)

Needs Node.js (nodejs.org, or `brew install node` / `winget install OpenJS.NodeJS` for
the LTS version). Then: `npx @modelcontextprotocol/inspector`. Set Transport Type to
"Streamable HTTP", URL to `http://localhost:8000/mcp`, connect, and call
`list_available_test_issues` first to see what fake data exists, before testing
`get_jira_issue` or `run_compliance_check` against it.

---

## Files everyone needs, regardless of setup

`comparison_engine.py`, `jira_client.py`, `fixtures.py`, `requirements.txt` — these are
the shared core. Docker-only additions: `Dockerfile`, `docker-compose.yml`,
`mcp_server.py`. Reference docs: `README.md`, `N8N_WORKFLOW.md`, `TEAM_PLAN.md`.

## Who's working on what (see `TEAM_PLAN.md` for full detail)

| Person | Focus | Setup needed |
|---|---|---|
| Jony | Notes vs proposal prompt tuning | Plain Python, or just claude.ai chat |
| Kamo | Proposal vs planning prompt tuning | Plain Python, or just claude.ai chat |
| Karabo | Planning vs ASD prompt tuning | Plain Python, or just claude.ai chat |
| Niral | Streamlit interface | Plain Python |
| Tevin | Check-in feature | Plain Python |
| Nathan | Integration, Jira/MCP/n8n | Full Docker stack |
| Sarah | Real task data, business writeup | No dev setup needed |
| Eugene | Testing rubric | No dev setup needed |
