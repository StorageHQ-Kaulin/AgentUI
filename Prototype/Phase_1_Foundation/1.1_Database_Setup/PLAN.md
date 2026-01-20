# 1.1 Database Setup

## Objective

Create a SQLite database with full schema to support the agent orchestrator system. This is the persistence layer that enables state management across all agents.

## Why SQLite?

- Zero deployment complexity (single file)
- ACID transactions (safe concurrent access)
- Built into Python standard library
- Query specific rows (vs loading entire JSON)
- Easy to backup/restore

## Files to Create

```
Visual/
├── db/
│   ├── __init__.py
│   ├── schema.sql           # Full DDL
│   ├── database.py          # Connection & core functions
│   ├── queries.py           # Named queries
│   └── models.py            # Python dataclasses matching tables
```

## Schema Definition

Based on SYSTEM_ARCHITECTURE.md and Graph.html data structures:

### schema.sql

```sql
-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phase TEXT DEFAULT 'interview',
    summary TEXT,
    problem TEXT,
    transcript TEXT,
    work_plan TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Components table (nodes in Graph.html)
CREATE TABLE IF NOT EXISTS components (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    parent_id TEXT,
    label TEXT NOT NULL,
    type TEXT DEFAULT 'node',
    status TEXT DEFAULT 'pending',
    x INTEGER DEFAULT 0,
    y INTEGER DEFAULT 0,
    summary TEXT,
    problem TEXT,
    goals TEXT,          -- JSON array
    scope TEXT,          -- JSON array
    requirements TEXT,   -- JSON array
    risks TEXT,          -- JSON array
    inputs TEXT,         -- JSON array
    outputs TEXT,        -- JSON array
    files TEXT,          -- JSON array
    subtasks TEXT,       -- JSON array
    agent_id TEXT,
    last_edited TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (parent_id) REFERENCES components(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Edges table (connections in Graph.html)
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    label TEXT,
    type TEXT DEFAULT 'data',  -- data, api, auth, schema, log
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (from_id) REFERENCES components(id),
    FOREIGN KEY (to_id) REFERENCES components(id)
);

-- Metrics table (supports weighted scoring from Graph.html)
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id TEXT NOT NULL,
    requirement TEXT NOT NULL,
    value TEXT,
    status TEXT DEFAULT 'pending',  -- pass, fail, pending
    weight REAL DEFAULT 1.0,
    FOREIGN KEY (component_id) REFERENCES components(id)
);

-- Test Cases table (from Graph.html testCases)
CREATE TABLE IF NOT EXISTS test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pass, fail, pending
    value TEXT,
    weight REAL DEFAULT 1.0,
    FOREIGN KEY (component_id) REFERENCES components(id)
);

-- Managers table
CREATE TABLE IF NOT EXISTS managers (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    component_id TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (component_id) REFERENCES components(id)
);

-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id TEXT NOT NULL,
    manager_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    logic TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    assigned_agent TEXT,
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (component_id) REFERENCES components(id),
    FOREIGN KEY (manager_id) REFERENCES managers(id),
    FOREIGN KEY (assigned_agent) REFERENCES agents(id)
);

-- Agents table
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    dept TEXT,           -- DISC, DES, MGT, DEV
    initials TEXT,
    manager_id TEXT,
    task_id INTEGER,
    status TEXT DEFAULT 'idle',  -- active, complete, pending, working, idle
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_active TEXT,
    FOREIGN KEY (manager_id) REFERENCES managers(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Logs table
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    component_id TEXT,
    task_id INTEGER,
    agent_id TEXT,
    action TEXT,
    message TEXT,
    level TEXT DEFAULT 'info',  -- debug, info, warn, error
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Global Tasks table (project-level phases from Graph.html)
CREATE TABLE IF NOT EXISTS global_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    text TEXT NOT NULL,
    done INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_components_project ON components(project_id);
CREATE INDEX IF NOT EXISTS idx_edges_project ON edges(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_component ON tasks(component_id);
CREATE INDEX IF NOT EXISTS idx_logs_project ON logs(project_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
```

## Implementation Steps

### Step 1: Create db/__init__.py
```python
from .database import Database
from .models import Project, Component, Edge, Agent, Task, Log

__all__ = ['Database', 'Project', 'Component', 'Edge', 'Agent', 'Task', 'Log']
```

### Step 2: Create db/models.py
```python
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import json

@dataclass
class Project:
    id: str
    name: str
    phase: str = 'interview'
    summary: Optional[str] = None
    problem: Optional[str] = None
    transcript: Optional[str] = None
    work_plan: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class Component:
    id: str
    project_id: str
    label: str
    parent_id: Optional[str] = None
    type: str = 'node'
    status: str = 'pending'
    x: int = 0
    y: int = 0
    summary: Optional[str] = None
    problem: Optional[str] = None
    goals: List[str] = field(default_factory=list)
    scope: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    files: List[dict] = field(default_factory=list)
    subtasks: List[dict] = field(default_factory=list)
    agent_id: Optional[str] = None
    last_edited: Optional[str] = None

    def to_graph_node(self) -> dict:
        """Convert to Graph.html node format"""
        return {
            'id': self.id,
            'label': self.label,
            'x': self.x,
            'y': self.y,
            'type': self.type,
            'agentId': self.agent_id,
            'status': self.status,
            'lastEdited': self.last_edited,
            'summary': self.summary,
            'problem': self.problem,
            'goals': self.goals,
            'scope': self.scope,
            'requirements': self.requirements,
            'risks': self.risks,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'files': self.files,
            'subtasks': self.subtasks
        }
```

### Step 3: Create db/database.py
```python
import sqlite3
import json
import os
from contextlib import contextmanager
from typing import List, Optional, Dict, Any

class Database:
    def __init__(self, db_path: str = 'orchestrator.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r') as f:
            schema = f.read()
        with self.connection() as conn:
            conn.executescript(schema)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # CRUD operations for each table...
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] schema.sql executes without errors
- [ ] Database class can be instantiated
- [ ] All CRUD operations work for `projects` table
- [ ] All CRUD operations work for `components` table
- [ ] All CRUD operations work for `edges` table
- [ ] All CRUD operations work for `agents` table
- [ ] All CRUD operations work for `tasks` table
- [ ] All CRUD operations work for `logs` table
- [ ] All CRUD operations work for `metrics` table
- [ ] All CRUD operations work for `test_cases` table
- [ ] All CRUD operations work for `global_tasks` table
- [ ] Foreign key constraints are enforced
- [ ] `to_graph_node()` produces valid Graph.html format
- [ ] Database survives concurrent access test

## Tests Required

### test_database.py

```python
import pytest
from db import Database, Project, Component, Edge

class TestDatabase:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / 'test.db'))

    def test_create_project(self, db):
        """Can create a project"""
        project = db.create_project('test', 'Test Project')
        assert project.id == 'test'
        assert project.name == 'Test Project'

    def test_create_component(self, db):
        """Can create a component linked to project"""
        db.create_project('proj1', 'Project 1')
        comp = db.create_component('comp1', 'proj1', 'My Component')
        assert comp.project_id == 'proj1'

    def test_foreign_key_constraint(self, db):
        """Cannot create component without valid project"""
        with pytest.raises(Exception):
            db.create_component('comp1', 'nonexistent', 'Bad Component')

    def test_graph_node_format(self, db):
        """Component converts to Graph.html format"""
        db.create_project('proj1', 'Project 1')
        comp = db.create_component('comp1', 'proj1', 'Test',
            goals=['Goal 1'], status='active')
        node = comp.to_graph_node()
        assert node['id'] == 'comp1'
        assert node['goals'] == ['Goal 1']
        assert node['status'] == 'active'

    def test_concurrent_access(self, db):
        """Database handles concurrent writes"""
        import threading
        errors = []

        def writer(n):
            try:
                db.create_project(f'proj_{n}', f'Project {n}')
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
```

## Integration with server.py

After completion, update `server.py` to use database:

```python
# Before (current)
output_path = os.path.join(os.getcwd(), 'graph_data.json')
with open(output_path, 'w') as f:
    json.dump(graph_data, f, indent=2)

# After (with database)
from db import Database
db = Database()
project = db.create_project(project_id, project_name)
for node in graph_data['nodes']:
    db.create_component_from_dict(project.id, node)
```

---

*Status: Pending*
*Estimated Complexity: Medium*
*Dependencies: None*
