---
plan_id: cursor-demo
status: in-progress
todos: [{"id":"c-1","content":"define schema","status":"pending","depends_on":[],"dod":"spec#schema"},{"id":"c-2","content":"add validator","status":"pending","depends_on":["c-1"],"dod":"spec#validator"},{"id":"c-3","content":"wire cli","status":"pending","depends_on":["c-2"],"dod":"spec#cli"}]
---

# Cursor plan demo

Three steps. All dependencies are declared explicitly in the frontmatter todos[], so
every field is a latch (high-confidence) extraction. There is no prose dependency
inference in this fixture — it exercises the pure-latch path.
