# Phase 3: Management Layer

## Overview

Phase 3 implements the work planning and task breakdown agents. The General Manager takes the approved architecture and creates a work plan, then spawns Component Managers to break down each component into specific tasks.

## Dependencies

- **Phase 2 Complete**: Architect agent, Dashboard integration working
- **User Approval**: Design must be approved before planning begins

## Sub-Tasks

| Sub-Task | Description | Status |
|----------|-------------|--------|
| 3.1 General Manager | Create work plan, spawn managers | Pending |
| 3.2 Component Managers | Break components into tasks | Pending |
| 3.3 Task Schema | Define task structure and lifecycle | Pending |

## Phase Exit Criteria

All conditions must be met before proceeding to Phase 4:

- [ ] General Manager creates project-wide work plan
- [ ] General Manager spawns Manager per component
- [ ] Component Managers break down work into tasks
- [ ] Tasks have clear acceptance criteria
- [ ] Task dependencies are mapped
- [ ] Task priorities are assigned
- [ ] Dashboard shows task breakdown view
- [ ] Tasks persist to database
- [ ] Can navigate from component to tasks

## Phase Tests

```
Phase_3_Management_Layer/
├── tests/
│   ├── test_general_manager.py
│   ├── test_component_manager.py
│   └── test_task_lifecycle.py
```

## Agent Hierarchy at This Phase

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    ┌──────────────────┐                          │
│                    │ GENERAL MANAGER  │                          │
│                    │  (one per proj)  │                          │
│                    └────────┬─────────┘                          │
│                             │                                    │
│                    creates work plan                             │
│                    spawns managers                               │
│                             │                                    │
│          ┌──────────────────┼──────────────────┐                 │
│          ▼                  ▼                  ▼                 │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐          │
│   │  MANAGER   │     │  MANAGER   │     │  MANAGER   │          │
│   │ (Comp A)   │     │ (Comp B)   │     │ (Comp C)   │          │
│   └─────┬──────┘     └─────┬──────┘     └─────┬──────┘          │
│         │                  │                  │                 │
│   breaks into         breaks into        breaks into            │
│   tasks               tasks              tasks                  │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│   ┌──────────┐       ┌──────────┐       ┌──────────┐            │
│   │  Tasks   │       │  Tasks   │       │  Tasks   │            │
│   │ (3-5)    │       │ (3-5)    │       │ (3-5)    │            │
│   └──────────┘       └──────────┘       └──────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Scoped Context Rules

| Agent | Can See | Cannot See |
|-------|---------|------------|
| General Manager | All components, approved design | Task details, agent logs |
| Component Manager | Own component, related edges | Other components' tasks |
| Task (later) | Single task details | Other tasks, manager state |

## Graph.html Task View (from Level2)

The Graph.html Level2 view shows task breakdown:

```javascript
// From Graph.html Level2 example
const Level2 = {
    nodes: [
        // Manager at top
        {
            id: 'MGR', label: 'Manager: Scrapers', x: 500, y: 50,
            type: 'root', agentId: 'MGR2', status: 'active',
            summary: "Managing scraper component...",
        },
        // Tasks below
        {
            id: 'T1', label: 'Task: Implement V1', x: 100, y: 300,
            type: 'node', agentId: 'A1', status: 'in_progress',
            summary: "Build primary scraper...",
            subtasks: [{title: "Code scrape_leads.js", logic: "..."}],
            files: [{name: 'scrape_leads.js', type: 'file'}]
        }
    ],
    edges: [
        {from: 'MGR', to: 'T1', label: 'Created', type: 'api'},
        {from: 'T1', to: 'T2', label: 'Depends', type: 'data'}
    ]
};
```

## Estimated Complexity

| Sub-Task | Complexity | Reason |
|----------|------------|--------|
| 3.1 General Manager | High | Orchestration, spawning managers |
| 3.2 Component Managers | Medium | Task breakdown, dependency mapping |
| 3.3 Task Schema | Low | Data structure definition |

---

*Status: Pending*
*Last Updated: 2026-01-14*
