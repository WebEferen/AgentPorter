---
name: "port-starts-new-port"
description: "A new port creates the workspace with porter.py init and starts the survey after it."
tags: ["port"]
runs: 3
max_turns: 40
timeout_seconds: 900
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:port upstream/textkit --to typescript
