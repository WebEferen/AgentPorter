---
name: "verify-flags-missing-marker"
description: "A recorded divergence without a DIVERGENCE(id) marker in the code is reported as a problem."
tags: ["verify"]
runs: 3
max_turns: 30
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:verify core
