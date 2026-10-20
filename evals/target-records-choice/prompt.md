---
name: "target-records-choice"
description: "With the user's answers in hand, the agent re-scores and records the choice with a note in the user's words."
tags: ["target", "smoke"]
runs: 3
max_turns: 25
timeout_seconds: 600
allowed_tools: ["Read", "Glob", "Grep", "Skill", "Agent", "TodoWrite"]
---

/agentporter:target

We already know the answers: the port will be called from our TypeScript services, the team knows TypeScript and Python, and there are no hard constraints. If TypeScript comes out on top, go with it.
