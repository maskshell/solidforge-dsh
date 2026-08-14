---
package: wp-demo
plan_id: wp-demo
---

# Work package demo

```json
[
  {"id":"w-1","title":"model","depends_on":[],"dod":"wp#w1","files":["model.py"]},
  {"id":"w-2","title":"check","depends_on":["w-1"],"dod":"wp#w2","files":["check.py"]},
  {"id":"w-3","title":"wire","depends_on":["w-2"],"dod":"wp#w3","files":["wire.py"]}
]
```

## Sequence

The json block is the latch. A prose note: w-3 also depends on w-1 (shared foundation).
That extra dep is semantic-infer (low-confidence), merged with the json block's w-2.
