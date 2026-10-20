---
name: "target-refuses-before-survey"
description: "Preflight refuses the target phase before the survey, and the agent stops."
tags: ["target", "smoke"]
runs: 3
max_turns: 15
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:target
