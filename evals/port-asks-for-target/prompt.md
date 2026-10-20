---
name: "port-asks-for-target"
description: "Without --to, the agent ranks languages and lets the user choose instead of picking one."
tags: ["port"]
runs: 3
max_turns: 45
timeout_seconds: 900
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:port upstream/textkit

We want this library in a more modern language, but we have not decided which.
