"""
Database class for Agent Orchestrator.
Provides SQLite connection and CRUD operations for all tables.
"""
import sqlite3
import json
import os
from contextlib import contextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime

from .models import (
    Project, Component, Edge, Agent, Task, Log,
    Manager, Metric, TestCase, GlobalTask
)


class Database:
    """SQLite database interface for the orchestrator."""

    def __init__(self, db_path: str = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to orchestrator.db
                    in the Visual directory.
        """
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), '..', 'orchestrator.db')
        self.db_path = os.path.abspath(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize database with schema."""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r') as f:
            schema = f.read()
        with self.connection() as conn:
            conn.executescript(schema)

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # =========================================================================
    # PROJECT OPERATIONS
    # =========================================================================

    def create_project(
        self,
        id: str,
        name: str,
        phase: str = 'interview',
        summary: str = None,
        problem: str = None,
        questions: List[str] = None
    ) -> Project:
        """Create a new project (or replace if exists)."""
        with self.connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO projects 
                   (id, name, phase, summary, problem, questions)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (id, name, phase, summary, problem, json.dumps(questions or []))
            )
        return self.get_project(id)

    def get_project(self, id: str) -> Optional[Project]:
        """Get a project by ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (id,)
            ).fetchone()
            if row:
                return self._row_to_project(row)
        return None

    def get_all_projects(self) -> List[Project]:
        """Get all projects."""
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
            return [self._row_to_project(row) for row in rows]

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        """Convert a database row to a Project object."""
        data = dict(row)
        # Parse JSON fields
        if data.get('questions'):
            try:
                data['questions'] = json.loads(data['questions'])
            except json.JSONDecodeError:
                data['questions'] = []
        else:
            data['questions'] = []
        return Project(**data)

    def update_project(self, id: str, updates: Dict[str, Any]) -> Optional[Project]:
        """Update a project."""
        allowed = {'name', 'phase', 'summary', 'problem', 'transcript', 'work_plan', 'questions'}
        filtered = {k: v for k, v in updates.items() if k in allowed}
        if not filtered:
            return self.get_project(id)

        # Serialize JSON fields
        if 'questions' in filtered:
            filtered['questions'] = json.dumps(filtered['questions'])

        set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
        values = list(filtered.values()) + [id]

        with self.connection() as conn:
            conn.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)
        return self.get_project(id)

    def delete_project(self, id: str) -> bool:
        """Delete a project and all related data."""
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (id,))
            return cursor.rowcount > 0

    # =========================================================================
    # COMPONENT OPERATIONS
    # =========================================================================

    def create_component(
        self,
        id: str,
        project_id: str,
        label: str,
        parent_id: str = None,
        type: str = 'node',
        status: str = 'pending',
        x: int = 0,
        y: int = 0,
        summary: str = None,
        problem: str = None,
        goals: List[str] = None,
        scope: List[str] = None,
        requirements: List[str] = None,
        risks: List[str] = None,
        inputs: List[str] = None,
        outputs: List[str] = None,
        files: List[Dict] = None,
        subtasks: List[Dict] = None,
        agent_id: str = None
    ) -> Component:
        """Create a new component (or replace if exists)."""
        with self.connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO components
                   (id, project_id, parent_id, label, type, status, x, y,
                    summary, problem, goals, scope, requirements, risks,
                    inputs, outputs, files, subtasks, agent_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    id, project_id, parent_id, label, type, status, x, y,
                    summary, problem,
                    json.dumps(goals or []),
                    json.dumps(scope or []),
                    json.dumps(requirements or []),
                    json.dumps(risks or []),
                    json.dumps(inputs or []),
                    json.dumps(outputs or []),
                    json.dumps(files or []),
                    json.dumps(subtasks or []),
                    agent_id
                )
            )
        return self.get_component(id)

    def get_component(self, id: str) -> Optional[Component]:
        """Get a component by ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM components WHERE id = ?", (id,)
            ).fetchone()
            if row:
                return self._row_to_component(row)
        return None

    def get_components_by_project(self, project_id: str) -> List[Component]:
        """Get all components for a project."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM components WHERE project_id = ? ORDER BY y, x",
                (project_id,)
            ).fetchall()
            return [self._row_to_component(row) for row in rows]

    def _row_to_component(self, row: sqlite3.Row) -> Component:
        """Convert a database row to a Component object."""
        data = dict(row)
        # Parse JSON fields
        for field in ['goals', 'scope', 'requirements', 'risks', 'inputs',
                      'outputs', 'files', 'subtasks']:
            if data.get(field):
                try:
                    data[field] = json.loads(data[field])
                except json.JSONDecodeError:
                    data[field] = []
            else:
                data[field] = []
        return Component(**data)

    def update_component(self, id: str, updates: Dict[str, Any]) -> Optional[Component]:
        """Update a component."""
        allowed = {
            'parent_id', 'label', 'type', 'status', 'x', 'y',
            'summary', 'problem', 'goals', 'scope', 'requirements', 'risks',
            'inputs', 'outputs', 'files', 'subtasks', 'agent_id'
        }
        filtered = {k: v for k, v in updates.items() if k in allowed}
        if not filtered:
            return self.get_component(id)

        # Serialize JSON fields
        json_fields = {'goals', 'scope', 'requirements', 'risks',
                       'inputs', 'outputs', 'files', 'subtasks'}
        for field in json_fields:
            if field in filtered:
                filtered[field] = json.dumps(filtered[field])

        set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
        values = list(filtered.values()) + [id]

        with self.connection() as conn:
            conn.execute(f"UPDATE components SET {set_clause} WHERE id = ?", values)
        return self.get_component(id)

    def delete_component(self, id: str) -> bool:
        """Delete a component."""
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM components WHERE id = ?", (id,))
            return cursor.rowcount > 0

    # =========================================================================
    # EDGE OPERATIONS
    # =========================================================================

    def create_edge(
        self,
        project_id: str,
        from_id: str,
        to_id: str,
        label: str = '',
        type: str = 'data'
    ) -> Edge:
        """Create a new edge."""
        with self.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO edges (project_id, from_id, to_id, label, type)
                   VALUES (?, ?, ?, ?, ?)""",
                (project_id, from_id, to_id, label, type)
            )
            edge_id = cursor.lastrowid
        return Edge(
            id=edge_id,
            project_id=project_id,
            from_id=from_id,
            to_id=to_id,
            label=label,
            type=type
        )

    def get_edges_by_project(self, project_id: str) -> List[Edge]:
        """Get all edges for a project."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM edges WHERE project_id = ?", (project_id,)
            ).fetchall()
            return [Edge(
                id=row['id'],
                project_id=row['project_id'],
                from_id=row['from_id'],
                to_id=row['to_id'],
                label=row['label'],
                type=row['type']
            ) for row in rows]

    def delete_edge(self, id: int) -> bool:
        """Delete an edge."""
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM edges WHERE id = ?", (id,))
            return cursor.rowcount > 0

    def delete_edges_by_project(self, project_id: str) -> int:
        """Delete all edges for a project."""
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM edges WHERE project_id = ?", (project_id,)
            )
            return cursor.rowcount

    # =========================================================================
    # AGENT OPERATIONS
    # =========================================================================

    def create_agent(
        self,
        id: str,
        name: str,
        dept: str = 'DEV',
        initials: str = None,
        manager_id: str = None,
        status: str = 'idle'
    ) -> Agent:
        """Create a new agent (or replace if exists)."""
        if initials is None:
            initials = name[:2].upper()
        with self.connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO agents (id, name, dept, initials, manager_id, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (id, name, dept, initials, manager_id, status)
            )
        return self.get_agent(id)

    def get_agent(self, id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE id = ?", (id,)
            ).fetchone()
            if row:
                return Agent(**dict(row))
        return None

    def get_agents_by_manager(self, manager_id: str) -> List[Agent]:
        """Get all agents for a manager."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM agents WHERE manager_id = ?", (manager_id,)
            ).fetchall()
            return [Agent(**dict(row)) for row in rows]

    def get_all_agents(self) -> List[Agent]:
        """Get all agents."""
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM agents").fetchall()
            return [Agent(**dict(row)) for row in rows]

    def update_agent(self, id: str, updates: Dict[str, Any]) -> Optional[Agent]:
        """Update an agent."""
        allowed = {'name', 'dept', 'initials', 'manager_id', 'task_id', 'status', 'last_active'}
        filtered = {k: v for k, v in updates.items() if k in allowed}
        if not filtered:
            return self.get_agent(id)

        set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
        values = list(filtered.values()) + [id]

        with self.connection() as conn:
            conn.execute(f"UPDATE agents SET {set_clause} WHERE id = ?", values)
        return self.get_agent(id)

    def delete_agent(self, id: str) -> bool:
        """Delete an agent."""
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM agents WHERE id = ?", (id,))
            return cursor.rowcount > 0

    # =========================================================================
    # TASK OPERATIONS
    # =========================================================================

    def create_task(
        self,
        component_id: str,
        title: str,
        manager_id: str = None,
        description: str = None,
        logic: str = None,
        status: str = 'pending',
        priority: int = 0,
        assigned_agent: str = None,
        created_by: str = None
    ) -> Task:
        """Create a new task."""
        with self.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO tasks
                   (component_id, manager_id, title, description, logic,
                    status, priority, assigned_agent, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (component_id, manager_id, title, description, logic,
                 status, priority, assigned_agent, created_by)
            )
            task_id = cursor.lastrowid
        return self.get_task(task_id)

    def get_task(self, id: int) -> Optional[Task]:
        """Get a task by ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (id,)
            ).fetchone()
            if row:
                return Task(**dict(row))
        return None

    def get_tasks_by_component(self, component_id: str) -> List[Task]:
        """Get all tasks for a component."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE component_id = ? ORDER BY priority DESC, id",
                (component_id,)
            ).fetchall()
            return [Task(**dict(row)) for row in rows]

    def get_tasks_by_manager(self, manager_id: str) -> List[Task]:
        """Get all tasks for a manager."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE manager_id = ? ORDER BY priority DESC, id",
                (manager_id,)
            ).fetchall()
            return [Task(**dict(row)) for row in rows]

    def update_task(self, id: int, updates: Dict[str, Any]) -> Optional[Task]:
        """Update a task."""
        allowed = {
            'manager_id', 'title', 'description', 'logic', 'status',
            'priority', 'assigned_agent', 'completed_at'
        }
        filtered = {k: v for k, v in updates.items() if k in allowed}
        if not filtered:
            return self.get_task(id)

        set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
        values = list(filtered.values()) + [id]

        with self.connection() as conn:
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        return self.get_task(id)

    def delete_task(self, id: int) -> bool:
        """Delete a task."""
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
            return cursor.rowcount > 0

    # =========================================================================
    # LOG OPERATIONS
    # =========================================================================

    def create_log(
        self,
        action: str,
        message: str,
        project_id: str = None,
        component_id: str = None,
        task_id: int = None,
        agent_id: str = None,
        level: str = 'info'
    ) -> Log:
        """Create a new log entry."""
        with self.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO logs
                   (project_id, component_id, task_id, agent_id, action, message, level)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (project_id, component_id, task_id, agent_id, action, message, level)
            )
            log_id = cursor.lastrowid
        return Log(
            id=log_id,
            project_id=project_id,
            component_id=component_id,
            task_id=task_id,
            agent_id=agent_id,
            action=action,
            message=message,
            level=level,
            timestamp=datetime.now().isoformat()
        )

    def get_logs_by_project(self, project_id: str, limit: int = 100) -> List[Log]:
        """Get logs for a project."""
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM logs WHERE project_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (project_id, limit)
            ).fetchall()
            return [Log(**dict(row)) for row in rows]

    def get_logs_by_agent(self, agent_id: str, limit: int = 100) -> List[Log]:
        """Get logs for an agent."""
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM logs WHERE agent_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (agent_id, limit)
            ).fetchall()
            return [Log(**dict(row)) for row in rows]

    # =========================================================================
    # MANAGER OPERATIONS
    # =========================================================================

    def create_manager(
        self,
        id: str,
        project_id: str,
        component_id: str,
        status: str = 'active',
        created_by: str = None
    ) -> Manager:
        """Create a new manager (or replace if exists)."""
        with self.connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO managers (id, project_id, component_id, status, created_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (id, project_id, component_id, status, created_by)
            )
        return self.get_manager(id)

    def get_manager(self, id: str) -> Optional[Manager]:
        """Get a manager by ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM managers WHERE id = ?", (id,)
            ).fetchone()
            if row:
                return Manager(**dict(row))
        return None

    def get_managers_by_project(self, project_id: str) -> List[Manager]:
        """Get all managers for a project."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM managers WHERE project_id = ?", (project_id,)
            ).fetchall()
            return [Manager(**dict(row)) for row in rows]

    # =========================================================================
    # METRIC OPERATIONS
    # =========================================================================

    def create_metric(
        self,
        component_id: str,
        requirement: str,
        value: str = None,
        status: str = 'pending',
        weight: float = 1.0
    ) -> Metric:
        """Create a new metric."""
        with self.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO metrics (component_id, requirement, value, status, weight)
                   VALUES (?, ?, ?, ?, ?)""",
                (component_id, requirement, value, status, weight)
            )
            metric_id = cursor.lastrowid
        return Metric(
            id=metric_id,
            component_id=component_id,
            requirement=requirement,
            value=value,
            status=status,
            weight=weight
        )

    def get_metrics_by_component(self, component_id: str) -> List[Metric]:
        """Get all metrics for a component."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM metrics WHERE component_id = ?", (component_id,)
            ).fetchall()
            return [Metric(**dict(row)) for row in rows]

    # =========================================================================
    # TEST CASE OPERATIONS
    # =========================================================================

    def create_test_case(
        self,
        component_id: str,
        name: str,
        status: str = 'pending',
        value: str = None,
        weight: float = 1.0
    ) -> TestCase:
        """Create a new test case."""
        with self.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO test_cases (component_id, name, status, value, weight)
                   VALUES (?, ?, ?, ?, ?)""",
                (component_id, name, status, value, weight)
            )
            test_id = cursor.lastrowid
        return TestCase(
            id=test_id,
            component_id=component_id,
            name=name,
            status=status,
            value=value,
            weight=weight
        )

    def get_test_cases_by_component(self, component_id: str) -> List[TestCase]:
        """Get all test cases for a component."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM test_cases WHERE component_id = ?", (component_id,)
            ).fetchall()
            return [TestCase(**dict(row)) for row in rows]

    # =========================================================================
    # GLOBAL TASK OPERATIONS
    # =========================================================================

    def create_global_task(
        self,
        project_id: str,
        text: str,
        done: bool = False,
        sort_order: int = 0
    ) -> GlobalTask:
        """Create a new global task."""
        with self.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO global_tasks (project_id, text, done, sort_order)
                   VALUES (?, ?, ?, ?)""",
                (project_id, text, 1 if done else 0, sort_order)
            )
            task_id = cursor.lastrowid
        return GlobalTask(
            id=task_id,
            project_id=project_id,
            text=text,
            done=done,
            sort_order=sort_order
        )

    def get_global_tasks_by_project(self, project_id: str) -> List[GlobalTask]:
        """Get all global tasks for a project."""
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM global_tasks WHERE project_id = ?
                   ORDER BY sort_order""",
                (project_id,)
            ).fetchall()
            return [GlobalTask(
                id=row['id'],
                project_id=row['project_id'],
                text=row['text'],
                done=bool(row['done']),
                sort_order=row['sort_order']
            ) for row in rows]

    def update_global_task(self, id: int, done: bool) -> bool:
        """Update a global task's done status."""
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE global_tasks SET done = ? WHERE id = ?",
                (1 if done else 0, id)
            )
            return cursor.rowcount > 0

    # =========================================================================
    # GRAPH DATA GENERATION
    # =========================================================================

    # =========================================================================
    # ALIAS METHODS (for compatibility with agent code)
    # =========================================================================

    def get_components(self, project_id: str) -> List[Component]:
        """Alias for get_components_by_project."""
        return self.get_components_by_project(project_id)

    def get_edges(self, project_id: str) -> List[Edge]:
        """Alias for get_edges_by_project."""
        return self.get_edges_by_project(project_id)

    def get_global_tasks(self, project_id: str) -> List[GlobalTask]:
        """Alias for get_global_tasks_by_project."""
        return self.get_global_tasks_by_project(project_id)

    def get_metrics(self, component_id: str) -> List[Metric]:
        """Alias for get_metrics_by_component."""
        return self.get_metrics_by_component(component_id)

    def get_test_cases(self, component_id: str) -> List[TestCase]:
        """Alias for get_test_cases_by_component."""
        return self.get_test_cases_by_component(component_id)

    def delete_components(self, project_id: str) -> int:
        """Delete all components for a project."""
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM components WHERE project_id = ?", (project_id,)
            )
            return cursor.rowcount

    def delete_edges(self, project_id: str) -> int:
        """Alias for delete_edges_by_project."""
        return self.delete_edges_by_project(project_id)

    def get_agents_for_project(self, project_id: str) -> List[Agent]:
        """Get all agents assigned to components in a project."""
        components = self.get_components_by_project(project_id)
        agent_ids = {c.agent_id for c in components if c.agent_id}
        return [self.get_agent(aid) for aid in agent_ids if self.get_agent(aid)]

    def mark_global_task_done(self, project_id: str, task_pattern: str) -> bool:
        """Mark a global task as done by matching text pattern."""
        with self.connection() as conn:
            cursor = conn.execute(
                """UPDATE global_tasks SET done = 1
                   WHERE project_id = ? AND text LIKE ?""",
                (project_id, f"%{task_pattern}%")
            )
            return cursor.rowcount > 0

    # =========================================================================
    # GRAPH DATA GENERATION
    # =========================================================================

    def get_graph_data(self, project_id: str) -> Dict[str, Any]:
        """
        Generate complete graph data for Graph.html visualization.

        Returns the full data structure expected by the frontend.
        """
        project = self.get_project(project_id)
        if not project:
            return None

        components = self.get_components_by_project(project_id)
        edges = self.get_edges_by_project(project_id)
        global_tasks = self.get_global_tasks_by_project(project_id)

        # Get agents that are assigned to components
        agent_ids = {c.agent_id for c in components if c.agent_id}
        agents = [self.get_agent(aid) for aid in agent_ids if aid]
        agents = [a for a in agents if a]  # Filter None

        # Build nodes with metrics and test cases
        nodes = []
        for comp in components:
            node = comp.to_graph_node()
            node['metrics'] = [m.to_dict() for m in self.get_metrics_by_component(comp.id)]
            node['testCases'] = [t.to_dict() for t in self.get_test_cases_by_component(comp.id)]
            nodes.append(node)

        return {
            'projectName': project.name,
            'projectSummary': project.summary or '',
            'projectProblem': project.problem or '',
            'questions': project.questions or [],
            'globalTasks': [gt.to_graph_task() for gt in global_tasks],
            'agents': [a.to_graph_agent() for a in agents],
            'nodes': nodes,
            'edges': [e.to_graph_edge() for e in edges],
            'timestamp': datetime.now().isoformat()
        }
