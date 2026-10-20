---
name: "deps-refuses-before-target"
description: "Preflight refuses deps while the target language is not chosen."
tags: ["deps", "smoke"]
runs: 3
max_turns: 15
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:deps
