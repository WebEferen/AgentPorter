---
name: "implement-resumes-at-task"
description: "Implementation resumes at the stored task instead of starting the unit over."
tags: ["implement", "stage-awareness"]
runs: 3
max_turns: 40
timeout_seconds: 900
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:implement
