# Documentation Update Workflow

Phase-by-phase workflow for maintaining project documentation.

## Phase 1: Analysis (Sequential)

Role: Documentation Writer

Memory Integration:

Search Context:

```text
mcp__graphiti__search_memory_facts(query="documentation status gaps", max_facts=5)
```

Store Context:

```text
mcp__graphiti__add_memory(name="Documentation Plan: [area]", episode_body="Updates needed: ..., Priority: ...", source_description="documentation plan")
```

Task: Identify what documentation needs updating

## Phase 2: Updates (Parallel if independent files)

Role: Documentation Writer

Memory Integration:

Store Context:

```text
mcp__graphiti__add_memory(name="Documentation Updated: [file]", episode_body="Changes: ..., Version: ...", source_description="documentation update")
```

For independent docs:

```text
Task(documentation-writer): Update implementation status
Task(documentation-writer): Update test coverage matrix
Task(documentation-writer): Update project tracker
```

Verify all updated docs are complete and accurate. If gaps found → return to Phase 1 for additional analysis.

## Phase 3: Review (Sequential)

Role: code-reviewer agent

Memory Integration:

Search Context:

```text
mcp__graphiti__search_memory_facts(query="documentation review history", max_facts=5)
```

Store Context:

```text
mcp__graphiti__add_memory(name="Documentation Review: [area]", episode_body="Review status: ..., Issues found: ..., Reviewer: code-reviewer", source_description="documentation review")
```

Task: Review all updated documentation for completeness, accuracy, and consistency.

Review Checklist:

- All planned updates from Phase 1 have been applied
- Technical terminology is used consistently across documents
- Cross-references point to existing, valid sections or files
- No orphaned or stale content remains
- Formatting and structure follow project conventions

If review finds issues → return to Phase 2, fix documentation, re-submit.

## Phase 4: Publication (Sequential)

Role: Documentation Writer

Memory Integration:

Search Context:

```text
mcp__graphiti__search_memory_facts(query="documentation publication checklist", max_facts=5)
```

Store Context:

```text
mcp__graphiti__add_memory(name="Documentation Published: [area]", episode_body="Published files: ..., Publication date: ..., Status: complete", source_description="documentation publication")
```

Task: Final validation and commit.

Validation Steps:

- All cross-references resolve correctly
- File paths and links are valid
- No placeholder or TODO content remains in published docs
- Change log or release notes updated if applicable

Commit changes with descriptive message summarizing documentation updates.
