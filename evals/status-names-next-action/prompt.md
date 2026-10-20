---
name: "status-names-next-action"
description: "Status reports the single next action from the state file."
tags: ["status", "smoke"]
runs: 3
max_turns: 10
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:status
