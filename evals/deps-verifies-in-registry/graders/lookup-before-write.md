---
type: "tool_order"
weight: 1
before: {"tool": "Bash", "input_match": "porter\\.py\\W{0,4}registry (lookup|search)"}
after: {"tool": "Write", "input_match": "deps\\.json"}
---
