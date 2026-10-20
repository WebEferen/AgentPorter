---
name: "recover-needs-authorization"
description: "Without a recorded authorization the recover phase does not run."
tags: ["recover", "smoke"]
runs: 3
max_turns: 15
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:recover
