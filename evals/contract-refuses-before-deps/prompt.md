---
name: "contract-refuses-before-deps"
description: "Preflight refuses the contract phase before deps is done."
tags: ["contract", "smoke"]
runs: 3
max_turns: 15
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:contract
