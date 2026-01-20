-- Agent Orchestrator Database Schema
-- SQLite database for persistent state management

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phase TEXT DEFAULT 'interview',
    summary TEXT,
    problem TEXT,
    transcript TEXT,
    work_plan TEXT,
    questions TEXT,      -- JSON array of verifying questions
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
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES components(id) ON DELETE SET NULL
);

-- Edges table (connections in Graph.html)
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    label TEXT,
    type TEXT DEFAULT 'data',  -- data, api, auth, schema, log
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (from_id) REFERENCES components(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES components(id) ON DELETE CASCADE
);

-- Metrics table (supports weighted scoring from Graph.html)
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id TEXT NOT NULL,
    requirement TEXT NOT NULL,
    value TEXT,
    status TEXT DEFAULT 'pending',  -- pass, fail, pending
    weight REAL DEFAULT 1.0,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

-- Test Cases table (from Graph.html testCases)
CREATE TABLE IF NOT EXISTS test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pass, fail, pending
    value TEXT,
    weight REAL DEFAULT 1.0,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

-- Managers table
CREATE TABLE IF NOT EXISTS managers (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    component_id TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
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
    FOREIGN KEY (manager_id) REFERENCES managers(id) ON DELETE SET NULL
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
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE,
    FOREIGN KEY (manager_id) REFERENCES managers(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_agent) REFERENCES agents(id) ON DELETE SET NULL
);

-- Update agents table foreign key after tasks exists
-- (handled via application logic since SQLite doesn't support ALTER for FK)

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
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Chat History table (for component/PRD chat conversations)
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    component_id TEXT,
    role TEXT NOT NULL,           -- 'user' or 'assistant'
    content TEXT NOT NULL,
    section TEXT,                 -- PRD section context (overview, scope, etc.)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_components_project ON components(project_id);
CREATE INDEX IF NOT EXISTS idx_components_parent ON components(parent_id);
CREATE INDEX IF NOT EXISTS idx_edges_project ON edges(project_id);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
CREATE INDEX IF NOT EXISTS idx_tasks_component ON tasks(component_id);
CREATE INDEX IF NOT EXISTS idx_tasks_manager ON tasks(manager_id);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(assigned_agent);
CREATE INDEX IF NOT EXISTS idx_logs_project ON logs(project_id);
CREATE INDEX IF NOT EXISTS idx_logs_agent ON logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_global_tasks_project ON global_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_metrics_component ON metrics(component_id);
CREATE INDEX IF NOT EXISTS idx_test_cases_component ON test_cases(component_id);
CREATE INDEX IF NOT EXISTS idx_managers_project ON managers(project_id);
CREATE INDEX IF NOT EXISTS idx_agents_manager ON agents(manager_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_project ON chat_history(project_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_component ON chat_history(component_id);

-- Trigger to update updated_at on projects
CREATE TRIGGER IF NOT EXISTS update_project_timestamp
AFTER UPDATE ON projects
BEGIN
    UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger to update last_edited on components
CREATE TRIGGER IF NOT EXISTS update_component_timestamp
AFTER UPDATE ON components
BEGIN
    UPDATE components SET last_edited = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
