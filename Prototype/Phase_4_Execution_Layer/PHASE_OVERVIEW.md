# Phase 4: Execution Layer

## Overview

Phase 4 implements Worker agents that actually execute tasks using Claude Code. This is where code gets written, files get created, and real progress happens.

## Dependencies

- **Phase 3 Complete**: Tasks exist with clear acceptance criteria
- **Claude Code CLI**: Must be installed and configured

## Sub-Tasks

| Sub-Task | Description | Status |
|----------|-------------|--------|
| 4.1 Worker Agent Framework | Base worker with tool access | Pending |
| 4.2 Claude Code Integration | Execute tasks via CLI | Pending |
| 4.3 Progress Tracking | Real-time status updates | Pending |

## Phase Exit Criteria

All conditions must be met before proceeding to Phase 5:

- [ ] Worker agents can read files
- [ ] Worker agents can write/create files
- [ ] Worker agents can execute shell commands
- [ ] Tasks execute via Claude Code CLI
- [ ] Acceptance criteria auto-verified where possible
- [ ] Progress updates in real-time to database
- [ ] Dashboard shows execution status
- [ ] Failed tasks can be retried
- [ ] Circuit breaker prevents runaway execution
- [ ] Rate limiting respects API limits

## Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Autonomous** | Agent executes without human approval | Simple, low-risk tasks |
| **Supervised** | Agent proposes, human approves | Complex or critical tasks |
| **Hybrid** | Auto for routine, supervised for risky | Default recommended mode |

## Worker Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        WORKER AGENT                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │   CONTEXT   │    │  EXECUTOR   │    │  REPORTER   │          │
│  │   LOADER    │───▶│  (Claude    │───▶│  (Progress  │          │
│  │             │    │   Code)     │    │   Updates)  │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
│        │                  │                  │                   │
│        ▼                  ▼                  ▼                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    TOOLS AVAILABLE                          ││
│  ├─────────────┬─────────────┬─────────────┬─────────────────┐ ││
│  │   Read      │   Write     │   Bash      │   Verify        │ ││
│  │   Files     │   Files     │   Commands  │   Criteria      │ ││
│  └─────────────┴─────────────┴─────────────┴─────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Scoped Context Principle

Workers receive ONLY:
- Their assigned task details
- Relevant file contents (not entire codebase)
- Component scope and requirements
- Their own execution logs

Workers do NOT see:
- Other workers' tasks or logs
- Manager-level planning
- Other components' code
- Full project history

## Integration with Graph.html

The terminal UI in Graph.html (`renderAgentControl`) shows:
- Session ID
- Iteration count
- Cost tracking
- Progress bar
- Criteria checklist
- Live logs
- Control buttons (Pause, Reassign, Context, PR)

Workers should emit data matching this UI:

```javascript
{
    sessionId: 'sess_abc123',
    iteration: 5,
    maxIterations: 20,
    cost: 2.34,
    maxCost: 10.00,
    progress: 45,
    criteria: [
        {text: 'Criterion 1', status: 'pass'},
        {text: 'Criterion 2', status: 'pending'}
    ],
    logs: [
        {time: '10:23:45', message: 'Reading file...'},
        {time: '10:23:46', message: 'Analyzing structure...'}
    ],
    status: 'active'  // 'active', 'paused', 'complete', 'failed'
}
```

## Estimated Complexity

| Sub-Task | Complexity | Reason |
|----------|------------|--------|
| 4.1 Worker Framework | High | Tool integration, sandboxing |
| 4.2 Claude Code Integration | High | CLI orchestration, error handling |
| 4.3 Progress Tracking | Medium | Real-time updates, persistence |

---

*Status: Pending*
*Last Updated: 2026-01-14*
