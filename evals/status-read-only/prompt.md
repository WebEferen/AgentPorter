---
name: "status-read-only"
description: "Status prints the board and changes nothing."
tags: ["status", "smoke"]
runs: 3
max_turns: 10
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:status
