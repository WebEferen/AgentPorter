---
name: "deps-verifies-in-registry"
description: "Candidate packages come from registry lookups, never from memory."
tags: ["deps"]
runs: 3
max_turns: 40
timeout_seconds: 900
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:deps
