# MIP AI Challenge — Compliance Assistant: Where We're At & Who's Doing What

Deadline: **9 October**. Today is 28 September — that's about 2 working weeks.

## What "the tool" actually does, in plain terms

At four points in a task's life, someone submits a document that's supposed to line up
with an earlier one:

1. A developer's **proposal** should cover what the **initial notes** asked for
2. The **planning comment** should cover what the (possibly amended) **proposal** agreed to
3. The finished **ASD** should match what the **planning comment** said would happen

The tool reads both documents at each of those points and tells you: what's missing,
what changed without explanation, and how confident it is in that judgment. It doesn't
replace a human review — it's meant to catch the obvious gaps early, before a task moves
further down the line with something missed.

## What "fine-tuning" means (for anyone who hasn't worked with AI models before)

The tool works by giving an AI model (Claude) a written instruction — a "prompt" — that
says roughly: *"here are two documents, tell me what's missing or inconsistent between
them."* That instruction isn't perfect on the first try. "Fine-tuning" here just means:
running real examples through it, checking whether the AI's answer actually matches what
a person would say, and adjusting the wording of the instruction until it does. It's
closer to editing a very detailed brief than to traditional coding — no programming
knowledge needed, just a good eye for what a "correct" answer to a compliance check
should look like.

## Test data — now available without waiting on Jira

We haven't received Jira/TST server access yet, so rather than everyone sitting idle,
we've built three complete fake example tasks (in `fixtures.py`) that stand in for real
Jira tickets. Each one has all four documents needed, and they're deliberately not all
"perfect" — some have a gap or an unexplained change on purpose, so there's something
real to catch, not just documents that always pass. Once real Jira access lands, we
switch a single setting and the tool starts reading from real tickets instead — nothing
else needs to change.

## Running the tool without an API key (for building/testing, not for real tuning)

The whole tool — the interface, the Jira connection, the automation — can run with
zero Anthropic API key, using a setting called mock mode. This is genuinely useful for
building and demoing the pipeline itself, but it does not do any real reviewing: it
gives back a placeholder answer clearly marked as fake, not a real judgment. Anyone
building the interface, the Jira connection, or the automation can work this way with
no blockers. Anyone actually judging whether the AI's answer is *correct*
(Jony, Kamo, Karabo) needs a real key — there's nothing genuine to check without one.

## Who's doing what

| Person | What they're fine-tuning | What that means day to day |
|---|---|---|
| **Jony** | The check between initial notes and the proposal | Read the notes and proposal for each fake task (and real ones once available), decide whether the AI's answer is right, adjust the instruction if it misses something or flags something that isn't really a problem |
| **Kamo** | The check between the proposal and the planning comment | Same idea, one stage later — proposal vs. what the developer actually planned to build |
| **Karabo** | The check between planning and the finished ASD | Same idea, at the final stage — did what was planned actually get built and tested |
| **Niral** | The chat-style interface (the actual screen the team uses) | Making the interface usable — adding the ability to pull a task in by number instead of pasting text, keeping track of more than one task at a time |
| **Tevin** | The check-in feature | A separate, smaller piece — periodically asking a developer what's changed on their task and keeping a log, rather than comparing two documents |
| **Nathan** | Everything fitting together | The core comparison logic, the Jira connection, and making sure everyone's piece works with everyone else's |
| **Sarah** | Real examples + the business case | Pulling actual completed tasks once Jira access allows, and writing up why this matters for whoever we present to |
| **Eugene** | What "good" looks like | Defining a simple checklist so the team isn't just eyeballing whether an AI answer is right — a consistent standard everyone can test against |

## Two-week plan

**This week (Sep 29 – Oct 3)**
- Jony, Kamo, Karabo start tuning their stage against the fake tasks in `fixtures.py`
  today — no need to wait for anything else
- Niral wires the interface to pull a task in by number (using the fake tasks for now)
- Tevin builds a first version of the check-in feature
- Nathan keeps the Jira connection and automation pieces ready so real access can be
  swapped in the moment it arrives
- Sarah keeps chasing real task examples and starts the write-up
- Eugene drafts the "what counts as correct" checklist so there's a shared standard by
  the time real data shows up

**Second week (Oct 6 – Oct 8)**
- Swap in real Jira data as soon as it's available and re-check everything against it
  — fake-task tuning is a head start, not a substitute for the real thing
- Full run-through: notes → proposal → planning → ASD, start to finish, on a real
  (or realistic) task
- Polish the demo — what we're actually going to show and say on the day

**Oct 9** — submission / demo day.

## What could slow this down

- **Jira/TST access still pending** — mitigated for now by the fake tasks, but real data
  is still needed before the second week to make sure the fake examples weren't
  accidentally too easy or too hard
- **Anthropic API access** — no longer blocks building or demoing the pipeline (mock
  mode covers that), but is still needed for Jony, Kamo, and Karabo's actual tuning work
  — being chased separately, a personal key is a quick fallback if the company one is
  delayed
