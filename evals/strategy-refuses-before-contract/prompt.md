---
name: "strategy-refuses-before-contract"
description: "Preflight refuses the strategy phase before the contract exists."
tags: ["strategy", "smoke"]
runs: 3
max_turns: 15
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:strategy
