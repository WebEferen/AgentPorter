---
name: "target-asks-user"
description: "The target phase scores languages and stops for the user's choice."
tags: ["target", "smoke"]
runs: 3
max_turns: 25
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:target
