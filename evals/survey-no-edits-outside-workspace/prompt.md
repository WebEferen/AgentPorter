---
name: "survey-no-edits-outside-workspace"
description: "The survey only writes inside .porter/."
tags: ["survey"]
runs: 3
max_turns: 30
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:survey
