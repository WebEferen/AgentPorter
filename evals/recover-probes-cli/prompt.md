---
name: "recover-probes-cli"
description: "The recover phase probes the CLI and records its surface in recovery.json."
tags: ["recover"]
runs: 3
max_turns: 40
timeout_seconds: 900
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:recover
