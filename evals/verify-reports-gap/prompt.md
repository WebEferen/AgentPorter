---
name: "verify-reports-gap"
description: "A fixture mismatch is reported as GAP, not as parity."
tags: ["verify"]
runs: 3
max_turns: 30
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:verify core
