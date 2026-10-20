---
name: "deps-stops-at-copyleft-gate"
description: "A strong copyleft source license is a gate item, and the agent stops for the user."
tags: ["deps"]
runs: 3
max_turns: 40
timeout_seconds: 900
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:deps
