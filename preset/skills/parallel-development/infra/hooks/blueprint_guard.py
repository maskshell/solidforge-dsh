#!/usr/bin/env python3
"""blueprint_guard.py — PreToolUse hook: enforce frozen read-only anchors.

Guards FOUR anchor kinds (distinct freeze signals, one deny path):
  - Intent Blueprint: paths under any `intent-blueprints/` dir ending in `.blueprint.md` (the Phase-0 convergence anchor).
    Freeze = frontmatter `status: frozen`.
  - Plan Queue: paths under any `plan-queues/` dir ending in `.queue.md` (plan-driven-mode anchor).
    Freeze = frontmatter `status: frozen`.
  - Design (external skill): any `DESIGN.md` (Impeccable; see references/external-skills.md).
    Freeze = side-car sentinel `.solidforge/loop/design.frozen` (DESIGN.md's frontmatter is an external token-export with no `status` field).
  - OpenAPI spec (external skill, Depth 2): any `openapi.{json,yaml,yml}` / `swagger.{json,yaml,yml}` (Spectral; see references/external-skills.md, ADR 23).
    Freeze = side-car sentinel `.solidforge/loop/openapi.frozen` (the spec is external-authored; frozen at Phase 0 so the implementer codes against a stable contract).

Each is FROZEN after its freeze step and must be read-only for the Coder mid-loop. The only legitimate change path is the Revision Channel.

Deterministic guard (freeze signal differs per kind):
  - blueprint / plan-queue: DENY if the target's YAML frontmatter has `status: frozen` (`status: revising` / missing / other, or a brand-new Write -> allow).
  - design (DESIGN.md): DENY if the side-car sentinel `.solidforge/loop/design.frozen` exists (DESIGN.md's frontmatter is an external token-export with no `status`).
  - openapi (spec): DENY if the side-car sentinel `.solidforge/loop/openapi.frozen` exists (same side-car model as design; the spec is external-authored).
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import detect_toolchain as dt  # noqa: E402

BLUEPRINT_RE = re.compile(r"(^|/)intent-blueprints/.+\.blueprint\.md$")
PLAN_QUEUE_RE = re.compile(r"(^|/)plan-queues/.+\.queue\.md$")
DESIGN_RE = re.compile(r"(^|/)DESIGN\.md$")
OPENAPI_RE = re.compile(r"(^|/)(openapi|swagger)\.(json|ya?ml)$")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
STATUS_RE = re.compile(r"^\s*status\s*:\s*['\"]?(\w+)['\"]?\s*$", re.MULTILINE)


def anchor_kind(path):
    """Return 'blueprint' | 'plan-queue' | 'design' | 'openapi' | None for a path."""
    if not path:
        return None
    if BLUEPRINT_RE.search(path):
        return "blueprint"
    if PLAN_QUEUE_RE.search(path):
        return "plan-queue"
    if DESIGN_RE.search(path):
        return "design"
    if OPENAPI_RE.search(path):
        return "openapi"
    return None


def frozen_status(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            head = fh.read(4096)
    except OSError:
        return None
    fm = FRONTMATTER_RE.match(head)
    if not fm:
        return None
    m = STATUS_RE.search(fm.group(1))
    return m.group(1) if m else None


def design_is_frozen():
    """The design anchor (DESIGN.md) is external/Impeccable-owned — its frontmatter has no `status`, so its freeze is a side-car sentinel next to loop-state, not frontmatter. Set at Phase 0, cleared at converge (orchestrator manages the sentinel). See references/external-skills.md."""
    return os.path.exists(os.path.join(dt.state_dir(), "design.frozen"))


def openapi_is_frozen():
    """The OpenAPI-spec anchor (Spectral, Depth 2) is external-authored, so its freeze is a side-car sentinel next to loop-state, not frontmatter. Set at Phase 0, cleared at converge (orchestrator manages the sentinel). See references/external-skills.md, ADR 23."""
    return os.path.exists(os.path.join(dt.state_dir(), "openapi.frozen"))


def deny(reason):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


DENY_MESSAGES = {
    "blueprint": (
        "Blueprint {path} is FROZEN and read-only (Intent Blueprint anchor). "
        "The Coder cannot edit it. To change intent, open the Blueprint Revision Channel: "
        "set frontmatter status to 'revising', escalate to Planner (requirements-manager/Plan) + human, revise, bump blueprint_version, then set status back to 'frozen'. "
        "See references/intent-blueprint.md."
    ),
    "plan-queue": (
        "Plan Queue {path} is FROZEN and read-only (plan-driven-mode anchor). "
        "The Coder cannot edit the plan interpretation mid-chain. To revise it, open the Revision Channel: set frontmatter status to 'revising', edit, bump queue_version, set status back to 'frozen', then run `plan_queue.py sync`. "
        "See references/plan-driven-mode.md."
    ),
    "design": (
        "DESIGN.md {path} is FROZEN (external-skill convergence anchor; freeze set via the side-car sentinel .solidforge/loop/design.frozen). The Coder cannot edit it mid-loop. To revise, open the Blueprint Revision Channel: the orchestrator clears the design freeze, revises DESIGN.md via /impeccable (document/extract), then re-freezes. See references/external-skills.md."
    ),
    "openapi": (
        "OpenAPI spec {path} is FROZEN (external-skill convergence anchor, Spectral Depth 2; freeze set via the side-car sentinel .solidforge/loop/openapi.frozen). The Coder cannot edit it mid-loop. To revise, open the Blueprint Revision Channel: the orchestrator clears the openapi freeze, revises the spec, then re-freezes. See references/external-skills.md, ADR 23."
    ),
}


def main():
    payload = dt.read_payload()
    tool = payload.get("tool_name", "")
    if tool.lower() not in ("edit", "write", "multiedit"):
        sys.exit(0)

    file_path = (payload.get("tool_input") or {}).get("file_path")
    kind = anchor_kind(file_path)
    if not kind:
        sys.exit(0)

    # The design anchor (DESIGN.md) is external-owned: its freeze is a side-car sentinel, not frontmatter `status` (DESIGN.md's frontmatter is an Impeccable token-export with no status).
    if kind == "design":
        if design_is_frozen():
            deny(DENY_MESSAGES["design"].format(path=file_path))
        sys.exit(0)

    # The openapi anchor (Spectral, Depth 2) is external-authored: same side-car sentinel model as design.
    if kind == "openapi":
        if openapi_is_frozen():
            deny(DENY_MESSAGES["openapi"].format(path=file_path))
        sys.exit(0)

    if frozen_status(file_path) == "frozen":
        deny(DENY_MESSAGES[kind].format(path=file_path))
    sys.exit(0)


if __name__ == "__main__":
    main()
