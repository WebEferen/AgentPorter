---
name: "strategy-stops-at-gate"
description: "The strategy phase ends at the user's approval, never self-approved."
tags: ["strategy"]
runs: 3
max_turns: 40
timeout_seconds: 900
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:strategy
