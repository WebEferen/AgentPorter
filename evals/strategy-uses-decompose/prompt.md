---
name: "strategy-uses-decompose"
description: "Units come from porter.py decompose, then the agent writes strategy.md."
tags: ["strategy"]
runs: 3
max_turns: 40
timeout_seconds: 900
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:strategy
