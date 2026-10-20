---
name: "status-no-workspace"
description: "Without a workspace, status says so and points to /agentporter:port."
tags: ["status", "smoke"]
runs: 3
max_turns: 10
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:status
