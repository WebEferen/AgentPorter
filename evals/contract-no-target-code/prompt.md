---
name: "contract-no-target-code"
description: "The contract phase writes nothing outside .porter/."
tags: ["contract"]
runs: 3
max_turns: 50
timeout_seconds: 900
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:contract
