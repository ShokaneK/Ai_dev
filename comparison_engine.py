"""
Comparison engine for the Patch and Task Compliance Assistant.

One reusable function, `compare_documents`, powers all four compliance stages:
  1. notes_vs_proposal      - initial Jira notes vs developer's proposal
  2. proposal_vs_amended    - proposal vs proposal amended after design session
  3. proposal_vs_planning   - proposal/design notes vs developer's planning comment
  4. planning_vs_asd        - planning + check-in history vs completed ASD

Each stage is just a different prompt template + a different pair of documents.
Swap the model name via ANTHROPIC_MODEL if needed; defaults to a current Sonnet model.

MOCK MODE: set USE_MOCK_CLAUDE=true (the default, so the whole build runs with zero
setup) to skip calling Claude entirely and get a clearly-labeled placeholder result
back instead. This lets every other piece — Streamlit, the MCP server, n8n, the
Jira/fixtures plumbing — be built, wired together, and demoed end to end with no
API key at all.

IMPORTANT — what mock mode does NOT give you: an actual compliance judgment. It
doesn't read the documents with any real understanding, so it can't tell you whether
a proposal actually misses something the notes asked for. Prompt tuning (Jony, Kamo,
Karabo's work) fundamentally needs a real key — a mocked answer has nothing to tune
against. Treat mock mode as "does the pipeline work," not "is the AI's judgment good."
Set USE_MOCK_CLAUDE=false (with a valid ANTHROPIC_API_KEY) the moment real judgment
is what's being checked.
"""

import os
import json
import hashlib
from dataclasses import dataclass, field
from typing import Optional


MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

# Default true: the whole build works with zero API key out of the box.
# Flip to false once real AI judgment (not just pipeline wiring) is what's needed.
MOCK_MODE = os.environ.get("USE_MOCK_CLAUDE", "true").lower() == "true"

# anthropic is imported only for real calls, so mock mode needs nothing beyond the
# Python standard library (no pip install required).
if MOCK_MODE:
    client = None
else:
    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env


@dataclass
class ComparisonResult:
    coverage_gaps: list = field(default_factory=list)
    deviations: list = field(default_factory=list)
    confidence: str = "unknown"      # "high" | "medium" | "low"
    summary: str = ""
    raw_response: Optional[str] = None
    parse_error: bool = False
    mocked: bool = False


# ---------------------------------------------------------------------------
# Prompt templates — one per compliance stage.
# Keep these as the thing your team iterates on most; the code around them
# shouldn't need to change once this is stable.
# ---------------------------------------------------------------------------

PROMPT_TEMPLATES = {
    "notes_vs_proposal": """You are reviewing a developer's proposal against the solution architect's
initial Jira notes for a task. The notes are a rough guideline, not a full spec, so some
elaboration by the developer is expected and fine.

Flag it as a genuine gap only when the proposal is missing something the notes explicitly
asked for, or clearly misunderstands the requirement. Do not flag reasonable extra detail,
different wording, or sensible technical choices the notes didn't specify.

--- INITIAL JIRA NOTES ---
{reference_doc}

--- DEVELOPER PROPOSAL ---
{new_doc}
""",

    "proposal_vs_amended": """You are comparing a developer's original proposal against the version
amended after the design session. Identify what changed, and flag anything the design
session raised that does NOT appear to have been addressed in the amended proposal.

--- ORIGINAL PROPOSAL ---
{reference_doc}

--- AMENDED PROPOSAL / DESIGN SESSION SUMMARY ---
{new_doc}
""",

    "proposal_vs_planning": """You are checking a developer's planning comment against the agreed
proposal (and design session notes, if included). Confirm that code changes, testing
methods, and affected programs from the proposal are accounted for in the planning comment.
Flag anything from the proposal that the planning comment does not address, and anything
in the planning comment that goes beyond or diverges from the proposal without explanation.

--- PROPOSAL / DESIGN NOTES ---
{reference_doc}

--- DEVELOPER PLANNING COMMENT ---
{new_doc}
""",

    # planning_vs_asd (Karabo): main job is catching planned work that quietly disappears.
    # Deviations are tagged [EXPLAINED]/[UNEXPLAINED] so the testing rubric can check them.
    "planning_vs_asd": """You are checking a completed ASD (the developer's record of what was
actually built and tested) against the planning comment for this task, plus any check-in
history. Confirm that the code changes and the testing described in the planning comment
were actually carried out, and separate explained changes from ones that quietly disappeared.

Check every code change and every test case in the planning comment's test plan. Treat a
planned item as covered only if the ASD clearly says it was done; do not assume it was done
just because related work was.

Classify what you find as follows:
- coverage_gaps: anything the planning comment committed to (a change or a test) that the
  ASD does not mention at all, and that is not explained anywhere in the ASD or the check-in
  history. These are the most serious findings; this check exists mainly to catch them.
- deviations: anything the ASD did differently from the plan, anything planned that was
  deferred or dropped with a stated reason, and any significant change in the ASD that the
  plan did not include. Start each one with [EXPLAINED] or [UNEXPLAINED]. A deviation counts
  as explained if a reason is given in the ASD itself or in the check-in history; say briefly
  where the explanation was found. Explained deviations are lower risk but still listed, so a
  reviewer can confirm the change was agreed.

Do not flag:
- different wording for the same change or test
- extra implementation detail in the ASD about a planned change
- items the ASD says were deferred or excluded when the planning comment never included them
  (those were settled before this stage; mention them in the summary only, if at all)

If no check-in history is included, judge from the planning comment and the ASD alone and do
not treat its absence as a problem. If the ASD does not describe the testing performed, list
each planned test as a coverage gap and set confidence to "low".

--- PLANNING COMMENT AND CHECK-IN HISTORY ---
{reference_doc}

--- COMPLETED ASD ---
{new_doc}
""",
}

OUTPUT_INSTRUCTIONS = """
Respond with ONLY a JSON object, no other text, no markdown fences. Use this exact shape:

{{
  "coverage_gaps": ["short specific gap description", ...],
  "deviations": ["short specific deviation description, note if explained or unexplained", ...],
  "confidence": "high" | "medium" | "low",
  "summary": "one or two sentence plain-language summary for a human reviewer"
}}

"confidence" reflects how confident you are in this assessment given the input quality,
not how compliant the task is. Use "low" if either document is too sparse to judge properly.
If there are no gaps or deviations, return empty lists — do not invent issues to fill them.
"""


def _mock_compare(
    reference_doc: str,
    new_doc: str,
    comparison_type: str,
    task_context: Optional[str],
) -> ComparisonResult:
    """
    Placeholder result used when MOCK_MODE is on — no call to Claude happens here.

    This does a crude word-overlap heuristic purely so the output isn't identical
    every time (useful for spotting whether the pipeline is passing the right
    documents through) — it is NOT a stand-in for real AI judgment. Every result
    is clearly labeled as mocked so it can't be mistaken for a real compliance check.
    """
    ref_words = set(w.lower().strip(".,;:()") for w in reference_doc.split() if len(w) > 4)
    new_words = set(w.lower().strip(".,;:()") for w in new_doc.split() if len(w) > 4)
    unmatched = sorted(ref_words - new_words)[:3]  # illustrative only, capped

    # Deterministic per-input "confidence" so repeated calls with the same input
    # look stable, rather than random, while still varying across different inputs.
    seed = int(hashlib.sha256((reference_doc + new_doc).encode()).hexdigest(), 16)
    confidence = ["low", "medium", "high"][seed % 3]

    gaps = (
        [f"[MOCK] Reference document mentions '{w}', not obviously echoed in the new document "
         f"(heuristic only, not a real AI judgment)." for w in unmatched]
        if unmatched else []
    )

    return ComparisonResult(
        coverage_gaps=gaps,
        deviations=[],
        confidence=confidence,
        summary=(
            f"[MOCK MODE — no Claude call made] This is a placeholder result for "
            f"comparison_type='{comparison_type}'"
            + (f", task_context='{task_context}'" if task_context else "")
            + ". Set USE_MOCK_CLAUDE=false with a valid ANTHROPIC_API_KEY for a real "
              "compliance judgment."
        ),
        raw_response=None,
        parse_error=False,
        mocked=True,
    )


def compare_documents(
    reference_doc: str,
    new_doc: str,
    comparison_type: str,
    task_context: Optional[str] = None,
) -> ComparisonResult:
    """
    Run one compliance comparison stage.

    comparison_type: one of "notes_vs_proposal", "proposal_vs_amended",
                      "proposal_vs_planning", "planning_vs_asd"
    task_context: optional free text (e.g. task number, client name) prepended for grounding
    """
    if comparison_type not in PROMPT_TEMPLATES:
        raise ValueError(
            f"Unknown comparison_type '{comparison_type}'. "
            f"Expected one of: {list(PROMPT_TEMPLATES.keys())}"
        )

    if MOCK_MODE:
        return _mock_compare(reference_doc, new_doc, comparison_type, task_context)

    prompt = PROMPT_TEMPLATES[comparison_type].format(
        reference_doc=reference_doc.strip(),
        new_doc=new_doc.strip(),
    )
    if task_context:
        prompt = f"Task context: {task_context.strip()}\n\n{prompt}"
    prompt += OUTPUT_INSTRUCTIONS

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    try:
        cleaned = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)
        return ComparisonResult(
            coverage_gaps=data.get("coverage_gaps", []),
            deviations=data.get("deviations", []),
            confidence=data.get("confidence", "unknown"),
            summary=data.get("summary", ""),
            raw_response=raw_text,
        )
    except (json.JSONDecodeError, AttributeError):
        return ComparisonResult(
            summary="Could not parse model output as JSON — see raw_response.",
            raw_response=raw_text,
            parse_error=True,
        )


if __name__ == "__main__":
    # Quick manual smoke test. Runs with zero setup by default (MOCK_MODE=true) —
    # you'll get a clearly-labeled placeholder result. Set USE_MOCK_CLAUDE=false
    # and ANTHROPIC_API_KEY in your environment for a real Claude-judged result.
    result = compare_documents(
        reference_doc="The client needs a validation added to the order entry screen "
                       "so that negative quantities are rejected before save.",
        new_doc="Proposal: add a check in the OrderEntry save trigger that rejects "
                "any line with quantity <= 0, returns a clear error message, and "
                "logs the rejection for audit purposes.",
        comparison_type="notes_vs_proposal",
        task_context="TASK-1234",
    )
    print(result)
