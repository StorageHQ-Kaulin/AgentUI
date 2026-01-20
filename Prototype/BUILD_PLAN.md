# Agent Orchestrator - Build Plan

## Project Vision

**Goal:** Build a system that can quickly understand any project through an AI-powered agent hierarchy that interviews, designs, plans, and executes autonomously.

**End State:** Point this system at any codebase/project and get:
- Structured understanding of the architecture
- Visual dependency graph
- Actionable task breakdown
- Autonomous agent execution (via Claude Code)

---

## Current State Analysis

### What Exists

| Component | Status | Location |
|-----------|--------|----------|
| Interview UI | Working (basic) | `Visual/Interview.html` |
| HTTP Server | Working | `Visual/server.py` |
| Agent Logic | Stub (heuristics only) | `Visual/agent_logic.py` |
| Dashboard/Graph | Working (visualization) | `Visual/Dashboard.html`, `Visual/Graph.html` |
| Design Docs | Complete | `Visual/SYSTEM_ARCHITECTURE.md`, `Visual/DESIGN_PHILOSOPHY.md` |
| Ralph Reference | Complete implementation | `Visual/ralph-claude-code/` |

### What's Missing

1. **Actual LLM Integration** - Current agent_logic.py uses keyword heuristics, not Claude
2. **Full Agent Hierarchy** - Only Interviewer + Architect stubs exist
3. **Database Layer** - No persistent state (only in-memory/JSON)
4. **General Manager + Managers** - Work planning agents don't exist
5. **Worker Agents** - No actual task execution
6. **Project Analysis** - Can't read/analyze existing codebases
7. **Scoped Context System** - Each agent should see only its scope

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENT ORCHESTRATOR                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [USER] ──▶ [INTERVIEW UI] ──▶ [SERVER API] ──▶ [ORCHESTRATOR]      │
│                                                     │                │
│                         ┌───────────────────────────┘                │
│                         ▼                                            │
│              ┌──────────────────┐                                    │
│              │   INTERVIEWER    │  Phase 1: Understand project       │
│              │   (Claude API)   │                                    │
│              └────────┬─────────┘                                    │
│                       ▼                                              │
│              ┌──────────────────┐                                    │
│              │    ARCHITECT     │  Phase 2: Design components        │
│              │   (Claude API)   │                                    │
│              └────────┬─────────┘                                    │
│                       ▼                                              │
│              ┌──────────────────┐                                    │
│              │    DASHBOARD     │  Phase 3: Human review/approval    │
│              │   (Graph.html)   │                                    │
│              └────────┬─────────┘                                    │
│                       ▼                                              │
│              ┌──────────────────┐                                    │
│              │ GENERAL MANAGER  │  Phase 4: Work planning            │
│              │   (Claude API)   │                                    │
│              └────────┬─────────┘                                    │
│                       ▼                                              │
│          ┌───────────┬───────────┐                                   │
│          ▼           ▼           ▼                                   │
│    ┌──────────┐┌──────────┐┌──────────┐                              │
│    │ MANAGER  ││ MANAGER  ││ MANAGER  │  Phase 5: Task breakdown     │
│    │(Comp A)  ││(Comp B)  ││(Comp C)  │                              │
│    └────┬─────┘└────┬─────┘└────┬─────┘                              │
│         ▼           ▼           ▼                                    │
│    ┌──────────┐┌──────────┐┌──────────┐                              │
│    │  AGENTS  ││  AGENTS  ││  AGENTS  │  Phase 6-7: Execute          │
│    │(Workers) ││(Workers) ││(Workers) │                              │
│    └──────────┘└──────────┘└──────────┘                              │
│                       │                                              │
│                       ▼                                              │
│              ┌──────────────────┐                                    │
│              │     SQLITE DB    │  Persistent state & logging        │
│              └──────────────────┘                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phased Build Plan

### Phase 1: Foundation (Start Here)

**Goal:** Replace heuristics with actual LLM integration and set up persistent storage.

#### 1.1 Database Setup
- [ ] Create SQLite database schema (from SYSTEM_ARCHITECTURE.md)
- [ ] Implement database module (`db.py`)
- [ ] Tables: `projects`, `components`, `edges`, `managers`, `tasks`, `agents`, `logs`
- [ ] Add migrations support for schema changes

**Files to create:**
```
Visual/
├── db/
│   ├── __init__.py
│   ├── schema.sql
│   ├── database.py      # SQLite connection & queries
│   └── migrations/
```

#### 1.2 Claude API Integration
- [ ] Create base agent class with Claude API calls
- [ ] Implement rate limiting (respect API limits)
- [ ] Add response parsing and validation
- [ ] Create prompt templates for each agent type

**Files to create:**
```
Visual/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py    # Abstract base with Claude API
│   ├── prompts/         # Prompt templates
│   │   ├── interviewer.txt
│   │   ├── architect.txt
│   │   └── ...
```

#### 1.3 Upgrade Interviewer Agent
- [ ] Replace heuristic logic with Claude API call
- [ ] Parse codebase files (if analyzing existing project)
- [ ] Generate structured project brief
- [ ] Store results in database

**Key Outputs:**
- Project brief JSON
- Identified components, technologies, patterns
- Questions for user clarification

---

### Phase 2: Design Pipeline

**Goal:** Implement full Architect agent that generates proper system designs.

#### 2.1 Architect Agent
- [ ] Create architect prompt template
- [ ] Input: Project brief + (optional) codebase analysis
- [ ] Output: Component tree with relationships
- [ ] Generate nodes and edges for graph visualization
- [ ] Store design in database

#### 2.2 Codebase Analysis
- [ ] Implement file scanner (glob patterns)
- [ ] Detect project type (Python, JS, etc.)
- [ ] Extract imports/dependencies
- [ ] Identify entry points and main components
- [ ] Generate dependency graph

**Files to create:**
```
Visual/
├── analyzers/
│   ├── __init__.py
│   ├── codebase_scanner.py
│   ├── dependency_analyzer.py
│   └── language_detectors/
│       ├── python.py
│       ├── javascript.py
│       └── ...
```

#### 2.3 Connect to Visualization
- [ ] Update server API to serve from database
- [ ] Add real-time updates via WebSocket (or polling)
- [ ] Enable user edits in Dashboard
- [ ] Save edits back to database

---

### Phase 3: Management Layer

**Goal:** Implement work planning and task breakdown agents.

#### 3.1 General Manager Agent
- [ ] Takes approved design as input
- [ ] Creates high-level work plan
- [ ] Determines execution order (respecting dependencies)
- [ ] Spawns Manager agents for each component
- [ ] Tracks overall progress

#### 3.2 Component Managers
- [ ] One Manager per top-level component
- [ ] Breaks component into specific tasks
- [ ] Prioritizes tasks within component
- [ ] Creates Worker Agents as needed
- [ ] Reports status to General Manager

#### 3.3 Task Schema
```json
{
  "id": "task_001",
  "component_id": "comp_auth",
  "title": "Implement login endpoint",
  "description": "Create POST /api/login with JWT...",
  "status": "pending|in_progress|blocked|complete",
  "priority": 1,
  "dependencies": ["task_000"],
  "assigned_agent": "agent_005",
  "estimated_complexity": "medium",
  "files_to_modify": ["src/routes/auth.py"],
  "acceptance_criteria": ["Returns JWT on success", "..."]
}
```

---

### Phase 4: Execution Layer

**Goal:** Implement Worker Agents that can actually perform tasks.

#### 4.1 Worker Agent Framework
- [ ] Create worker agent base class
- [ ] Implement scoped context (agent sees only its task)
- [ ] Add tool access (read files, write files, run commands)
- [ ] Implement status reporting

#### 4.2 Integration with Claude Code
- [ ] Use Claude Code CLI for actual code execution
- [ ] Pass scoped context to Claude Code
- [ ] Capture outputs and logs
- [ ] Handle errors and retries

**Two execution modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| **Autonomous** | Worker agents use Claude Code CLI directly | Code generation, file edits |
| **Supervised** | Workers propose changes, human approves | Critical systems, learning |

#### 4.3 Progress Tracking
- [ ] Real-time status updates to database
- [ ] Log all agent actions
- [ ] Track file changes per task
- [ ] Update Dashboard with live status

---

### Phase 5: Integration & Polish

**Goal:** Connect all pieces into a seamless workflow.

#### 5.1 End-to-End Flow
- [ ] User describes project → Interview → Design → Approve → Plan → Execute
- [ ] Handle interruptions gracefully (resume capability)
- [ ] Implement circuit breaker (from Ralph) to prevent runaway loops

#### 5.2 Project Import Modes

| Mode | Input | Output |
|------|-------|--------|
| **New Project** | User description | Full scaffold + implementation |
| **Analyze Existing** | Path to codebase | Architecture diagram + docs |
| **Enhance Project** | Codebase + feature request | Targeted changes |

#### 5.3 Dashboard Enhancements
- [ ] Real-time agent activity feed
- [ ] Click-to-expand task details
- [ ] Manual task reassignment
- [ ] Pause/resume controls
- [ ] Export/share architecture diagrams

---

## Recommended Starting Point

### Why Start with Phase 1.1 (Database)?

1. **Foundation for everything** - All agents need to read/write state
2. **Immediate value** - Can persist graphs between sessions
3. **Low risk** - Database layer is independent, easy to test
4. **Enables parallelism** - Once DB exists, multiple agents can work concurrently

### First Implementation Steps

```
Step 1: Create db/schema.sql with full schema
Step 2: Create db/database.py with CRUD operations
Step 3: Update server.py to use database instead of JSON file
Step 4: Test: Interview → Save to DB → Dashboard reads from DB
```

### Quick Win Path

If you want visible progress fast:

1. **Upgrade Interviewer** (1.3) - Replace heuristics with Claude API
2. **This alone** gives you AI-powered project analysis
3. **Then** add database for persistence
4. **Then** build out the hierarchy

---

## Technical Decisions

### Why SQLite?
- Zero deployment complexity (single file)
- ACID transactions (safe concurrent access)
- Built into Python standard library
- Query specific rows (vs loading entire JSON)
- Easy to backup/restore

### Why Claude API vs Claude Code CLI?
| Use Case | Recommendation |
|----------|----------------|
| Planning/Analysis | Claude API (structured JSON responses) |
| Code Execution | Claude Code CLI (file access, shell commands) |
| Hybrid | API for thinking, CLI for doing |

### Scoped Context Implementation
Each agent receives ONLY:
- Its assigned task/component
- Relevant file contents (not entire codebase)
- Immediate dependencies
- Its own logs (not other agents')

This prevents hallucinations and reduces token usage.

---

## File Structure (Target State)

```
Agent_Orchestrator/
├── Visual/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── interviewer.py
│   │   ├── architect.py
│   │   ├── general_manager.py
│   │   ├── manager.py
│   │   └── worker.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.sql
│   │   ├── database.py
│   │   └── queries.py
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── codebase_scanner.py
│   │   └── dependency_analyzer.py
│   ├── prompts/
│   │   ├── interviewer.txt
│   │   ├── architect.txt
│   │   ├── general_manager.txt
│   │   ├── manager.txt
│   │   └── worker.txt
│   ├── Dashboard.html
│   ├── Interview.html
│   ├── Graph.html
│   ├── server.py
│   └── orchestrator.py      # Main entry point
├── BUILD_PLAN.md            # This file
├── README.md
└── requirements.txt
```

---

## Success Metrics

### MVP (Minimum Viable Product)
- [ ] Can interview user about new project idea
- [ ] Generates visual architecture diagram
- [ ] Breaks down into actionable tasks
- [ ] Tasks are detailed enough for Claude Code execution

### Full Product
- [ ] Can analyze existing codebase automatically
- [ ] Agents execute tasks autonomously
- [ ] Real-time progress dashboard
- [ ] Handles errors gracefully with retry/recovery
- [ ] Scoped context prevents agent confusion

---

## Reference Implementation Notes

The **ralph-claude-code** folder contains a mature autonomous AI development loop. Key patterns to adopt:

1. **Circuit Breaker** - Prevents runaway loops
2. **Rate Limiting** - Respects API limits
3. **Session Management** - Maintains context across iterations
4. **Exit Detection** - Knows when to stop
5. **Logging** - Comprehensive audit trail

---

## Next Steps

1. **Confirm this plan** - Any adjustments needed?
2. **Pick starting point** - Database (1.1) or Interviewer upgrade (1.3)?
3. **Set up Claude API** - Ensure API key is available
4. **Begin implementation** - Agents will handle the coding

---

*Last Updated: 2026-01-14*
*Status: Planning Complete - Ready for Implementation*
