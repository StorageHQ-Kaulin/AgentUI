# Phase 2: Design Pipeline

## Overview

Phase 2 transforms the Interviewer's project brief into a detailed system architecture. The Architect agent analyzes requirements and generates a component tree with dependencies, while the Codebase Analyzer enables understanding of existing projects.

## Dependencies

- **Phase 1 Complete**: Database, Claude API, Interviewer Agent all working

## Sub-Tasks

| Sub-Task | Description | Status |
|----------|-------------|--------|
| 2.1 Architect Agent | Design system architecture from brief | Complete |
| 2.2 Codebase Analyzer | Scan and understand existing code | Complete |
| 2.3 Dashboard Integration | Real-time updates from database | Complete |

## Phase Exit Criteria

All conditions must be met before proceeding to Phase 3:

- [x] Architect agent generates detailed component trees
- [x] Components have proper parent/child relationships
- [x] Edges correctly represent data flow and dependencies
- [x] Codebase analyzer can scan Python projects
- [x] Codebase analyzer can scan JavaScript projects
- [x] Detected components match actual project structure
- [x] Dashboard reads data from SQLite database
- [x] Dashboard updates reflect database changes
- [x] User can approve/reject design in Dashboard (via /api/projects/:id/approve)

## Phase Tests

```
Phase_2_Design_Pipeline/
├── tests/
│   ├── test_architect.py        # Architecture generation
│   ├── test_codebase_scanner.py # File scanning
│   └── test_dashboard_api.py    # API integration
```

## Data Flow

```
┌─────────────────┐
│   Interviewer   │
│     (Phase 1)   │
└────────┬────────┘
         │ project_brief
         ▼
┌─────────────────┐     ┌─────────────────┐
│    Architect    │◄────│    Codebase     │
│     Agent       │     │    Analyzer     │
└────────┬────────┘     └─────────────────┘
         │                    (optional)
         │ component_tree
         ▼
┌─────────────────┐
│    Dashboard    │
│  (Graph.html)   │
└────────┬────────┘
         │ user_approval
         ▼
┌─────────────────┐
│ General Manager │
│    (Phase 3)    │
└─────────────────┘
```

## Graph.html Integration Points

The Architect must generate data matching these Graph.html structures:

### Node Properties for Architecture
```javascript
{
    // Hierarchical relationships
    id: 'comp_1',
    parent_id: 'ROOT',       // For nesting

    // Position for layout
    x: 500,
    y: 200,

    // Rich metadata
    summary: 'Component description',
    problem: 'What issue this solves',
    goals: ['Goal 1', 'Goal 2'],
    scope: ['What this component covers'],
    requirements: ['Functional requirements'],
    risks: ['Potential issues'],

    // Data flow
    inputs: ['Data this receives'],
    outputs: ['Data this produces'],

    // Trackable items
    metrics: [
        { req: 'Performance', value: 'TBD', status: 'pending', weight: 2 }
    ],
    testCases: [
        { name: 'Unit test', status: 'pending', weight: 1 }
    ]
}
```

### Edge Types for Dependencies
```javascript
// From Graph.html legend
const EDGE_TYPES = {
    'data': '#2ecc71',    // Data flow (green)
    'api': '#3498db',     // API calls (blue)
    'auth': '#e74c3c',    // Auth/security (red)
    'schema': '#f1c40f',  // Schema definitions (yellow)
    'log': '#95a5a6'      // Logging (gray)
};
```

## Estimated Complexity

| Sub-Task | Complexity | Reason |
|----------|------------|--------|
| 2.1 Architect Agent | High | Complex prompt engineering, tree generation |
| 2.2 Codebase Analyzer | High | Multi-language support, dependency detection |
| 2.3 Dashboard Integration | Medium | API endpoints, WebSocket potential |

---

*Status: Complete*
*Last Updated: 2026-01-15*
