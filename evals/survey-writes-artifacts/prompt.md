---
name: "survey-writes-artifacts"
description: "The survey runs between preflight and postflight and leaves survey.json and survey.md."
tags: ["survey"]
runs: 3
max_turns: 30
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:survey
