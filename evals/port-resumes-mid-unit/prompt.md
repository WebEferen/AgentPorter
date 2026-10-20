---
name: "port-resumes-mid-unit"
description: "With no arguments and a workspace present, the router resumes at the recorded unit and task."
tags: ["port", "stage-awareness", "smoke"]
runs: 3
max_turns: 25
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:port
