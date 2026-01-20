# Agent Dashboard - System Architecture

## Project Lifecycle

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                  PROJECT LIFECYCLE                                    │
├───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬─────────────┤
│ INTERVIEW │  DESIGN   │ VISUALIZE │   PLAN    │ BREAKDOWN │  ASSIGN   │   EXECUTE   │
│ (Phase 1) │ (Phase 2) │ (Phase 3) │ (Phase 4) │ (Phase 5) │ (Phase 6) │  (Phase 7)  │
├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼─────────────┤
│Interviewer│ Architect │ Dashboard │  General  │  Manager  │  Manager  │   Agents    │
│           │           │   (UI)    │  Manager  │  (each)   │→ Agents   │ → Tasks     │
└───────────┴───────────┴───────────┴───────────┴───────────┴───────────┴─────────────┘
```

---

## Agent Hierarchy

```
                    ┌─────────────────┐
                    │   INTERVIEWER   │  Phase 1
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │    ARCHITECT    │  Phase 2
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ GENERAL MANAGER │  Phase 4
                    │  (builds plan,  │
                    │ creates managers)│
                    └────────┬────────┘
                             ▼
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   ┌────────────┐     ┌────────────┐     ┌────────────┐
   │  MANAGER   │     │  MANAGER   │     │  MANAGER   │  Phase 5
   │ (Component │     │ (Component │     │ (Component │
   │     A)     │     │     B)     │     │     C)     │
   └─────┬──────┘     └─────┬──────┘     └─────┬──────┘
         ▼                  ▼                  ▼
   ┌─────┴─────┐      ┌─────┴─────┐      ┌─────┴─────┐
   │  AGENTS   │      │  AGENTS   │      │  AGENTS   │  Phase 6-7
   │ (assigned │      │ (assigned │      │ (assigned │
   │  to tasks)│      │  to tasks)│      │  to tasks)│
   └───────────┘      └───────────┘      └───────────┘
```

---

## Phase Descriptions

### Phase 1: Interview
**Role:** `interviewer`
- Conducts structured conversation with user
- Asks clarifying questions, edge cases
- Produces project brief/transcript

### Phase 2: Design  
**Role:** `architect`
- Takes interview transcript
- Creates component tree (modules/folders)
- Defines dependencies and success criteria

### Phase 3: Visualization
**Component:** Dashboard (Graph.html)
- User reviews flowchart
- Approves or requests changes

### Phase 4: Work Planning
**Role:** `general-manager`
- Reviews approved design
- Creates work plan
- Spawns and assigns managers to components

### Phase 5: Task Breakdown
**Role:** `manager` (one per component)
- Reads component scope/requirements
- Breaks into specific tasks
- Creates tasks in DB

### Phase 6: Agent Assignment
**Role:** `manager` (continues)
- Creates and assigns agents to tasks
- Sets priorities and deadlines

### Phase 7: Execution
**Role:** `agent` (many, tied to tasks)
- Each agent is assigned to specific task(s)
- Executes implementation
- Reports status/completion
- Logs progress

---

## Agent Roles Table

| Role | Scope | Reads | Writes |
|------|-------|-------|--------|
| `interviewer` | Project | - | `projects`, `transcripts` |
| `architect` | Project | `transcripts` | `components`, `edges` |
| `general-manager` | Project | `components` | `managers`, `work_plan` |
| `manager` | Component | `components` | `tasks`, `agents` |
| `agent` | Task(s) | `tasks` | `tasks`, `logs` |
| Dashboard | All | Everything | - |

---

## Database Schema

### `projects`
```sql
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  phase TEXT DEFAULT 'interview',
  transcript TEXT,
  work_plan TEXT,
  created_at TEXT,
  updated_at TEXT
);
```

### `components`
```sql
CREATE TABLE components (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  parent_id TEXT,
  label TEXT NOT NULL,
  type TEXT DEFAULT 'folder',
  status TEXT DEFAULT 'pending',
  goal TEXT,
  problem TEXT,
  scope TEXT,
  requirements TEXT,
  assigned_manager TEXT,
  x INTEGER,
  y INTEGER,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

### `edges`
```sql
CREATE TABLE edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  from_id TEXT NOT NULL,
  to_id TEXT NOT NULL,
  label TEXT,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

### `managers`
```sql
CREATE TABLE managers (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  component_id TEXT NOT NULL,
  status TEXT DEFAULT 'active',
  created_by TEXT,
  created_at TEXT,
  FOREIGN KEY (component_id) REFERENCES components(id)
);
```

### `tasks`
```sql
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  component_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'pending',
  priority INTEGER DEFAULT 0,
  assigned_agent TEXT,
  created_by TEXT,
  created_at TEXT,
  completed_at TEXT,
  FOREIGN KEY (component_id) REFERENCES components(id)
);
```

### `agents`
```sql
CREATE TABLE agents (
  id TEXT PRIMARY KEY,
  manager_id TEXT NOT NULL,
  task_id INTEGER,
  status TEXT DEFAULT 'idle',
  created_at TEXT,
  last_active TEXT,
  FOREIGN KEY (manager_id) REFERENCES managers(id),
  FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### `logs`
```sql
CREATE TABLE logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT,
  component_id TEXT,
  task_id INTEGER,
  agent_id TEXT,
  action TEXT,
  message TEXT,
  timestamp TEXT
);
```

---

## API Endpoints

### Project Level
| Method | Endpoint | Used By |
|--------|----------|---------|
| `POST` | `/api/project` | interviewer |
| `PATCH` | `/api/project/:id` | general-manager |
| `GET` | `/api/project/:id` | dashboard |

### Component Level
| Method | Endpoint | Used By |
|--------|----------|---------|
| `POST` | `/api/component` | architect |
| `GET` | `/api/component/:id` | manager |
| `PATCH` | `/api/component/:id` | manager |

### Manager Level
| Method | Endpoint | Used By |
|--------|----------|---------|
| `POST` | `/api/manager` | general-manager |
| `GET` | `/api/manager/:id` | manager |

### Task Level
| Method | Endpoint | Used By |
|--------|----------|---------|
| `POST` | `/api/task` | manager |
| `GET` | `/api/tasks?component=:id` | agents |
| `PATCH` | `/api/task/:id` | agent |

### Agent Level
| Method | Endpoint | Used By |
|--------|----------|---------|
| `POST` | `/api/agent` | manager |
| `GET` | `/api/agent/:id/tasks` | agent |
| `PATCH` | `/api/agent/:id` | agent |

---

## Workflow Example

```
User: "I want to build a lead enrichment scraper"
           │
           ▼
┌─────────────────────┐
│    INTERVIEWER      │ ──► project_brief.md
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│     ARCHITECT       │ ──► Components (CSV_Dumps, Scrapers, Output)
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│     DASHBOARD       │ ◄── User reviews & approves
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  GENERAL MANAGER    │ ──► Work plan + creates Managers
└─────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌────────┐   ┌────────┐
│Manager │   │Manager │ ──► Tasks
│(Scrape)│   │(Output)│
└───┬────┘   └───┬────┘
    │            │
    ▼            ▼
┌────────┐   ┌────────┐
│ Agent  │   │ Agent  │ ──► Execute tasks
│(Task 1)│   │(Task 3)│
└────────┘   └────────┘
```

---

## Key Principle: Scoped Context

| Role | Sees Only |
|------|-----------|
| Interviewer | User conversation |
| Architect | Interview transcript |
| General Manager | Design components |
| Manager | Their component + tasks |
| Agent | Their assigned task(s) |
| Dashboard | Everything (for humans) |
