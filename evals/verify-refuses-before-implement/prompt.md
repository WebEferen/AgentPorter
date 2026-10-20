---
name: "verify-refuses-before-implement"
description: "Verify refuses to run before any unit is implemented."
tags: ["verify", "smoke"]
runs: 3
max_turns: 15
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:verify
