"""
Data models for Agent Orchestrator.
Dataclasses that map to database tables and support Graph.html format.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


@dataclass
class Project:
    """Represents a project in the orchestrator."""
    id: str
    name: str
    phase: str = 'interview'
    summary: Optional[str] = None
    problem: Optional[str] = None
    transcript: Optional[str] = None
    transcript: Optional[str] = None
    work_plan: Optional[str] = None
    questions: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'phase': self.phase,
            'summary': self.summary,
            'problem': self.problem,
            'transcript': self.transcript,
            'transcript': self.transcript,
            'work_plan': self.work_plan,
            'questions': self.questions,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


@dataclass
class Component:
    """Represents a component/node in the system architecture."""
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
    files: List[Dict] = field(default_factory=list)
    subtasks: List[Dict] = field(default_factory=list)
    agent_id: Optional[str] = None
    last_edited: Optional[str] = None

    def to_graph_node(self) -> Dict[str, Any]:
        """Convert to Graph.html node format."""
        return {
            'id': self.id,
            'label': self.label,
            'x': self.x,
            'y': self.y,
            'type': self.type,
            'agentId': self.agent_id,
            'status': self.status,
            'lastEdited': self.last_edited,
            'summary': self.summary or '',
            'problem': self.problem or '',
            'goals': self.goals,
            'scope': self.scope,
            'requirements': self.requirements,
            'risks': self.risks,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'files': self.files,
            'subtasks': self.subtasks,
            'metrics': [],  # Loaded separately
            'testCases': []  # Loaded separately
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'parent_id': self.parent_id,
            'label': self.label,
            'type': self.type,
            'status': self.status,
            'x': self.x,
            'y': self.y,
            'summary': self.summary,
            'problem': self.problem,
            'goals': self.goals,
            'scope': self.scope,
            'requirements': self.requirements,
            'risks': self.risks,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'files': self.files,
            'subtasks': self.subtasks,
            'agent_id': self.agent_id,
            'last_edited': self.last_edited
        }


@dataclass
class Edge:
    """Represents a connection between components."""
    id: Optional[int]
    project_id: str
    from_id: str
    to_id: str
    label: str = ''
    type: str = 'data'  # data, api, auth, schema, log

    def to_graph_edge(self) -> Dict[str, Any]:
        """Convert to Graph.html edge format."""
        return {
            'from': self.from_id,
            'to': self.to_id,
            'label': self.label,
            'type': self.type
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'from': self.from_id,
            'to': self.to_id,
            'label': self.label,
            'type': self.type
        }


@dataclass
class Metric:
    """Represents a requirement metric for a component."""
    id: Optional[int]
    component_id: str
    requirement: str
    value: Optional[str] = None
    status: str = 'pending'  # pass, fail, pending
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'req': self.requirement,
            'value': self.value or '',
            'status': self.status,
            'weight': self.weight
        }


@dataclass
class TestCase:
    """Represents a test case for a component."""
    id: Optional[int]
    component_id: str
    name: str
    status: str = 'pending'  # pass, fail, pending
    value: Optional[str] = None
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'status': self.status,
            'value': self.value or '',
            'weight': self.weight
        }


@dataclass
class Manager:
    """Represents a component manager agent."""
    id: str
    project_id: str
    component_id: str
    status: str = 'active'
    created_by: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'component_id': self.component_id,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at
        }


@dataclass
class Agent:
    """Represents a worker agent."""
    id: str
    name: str
    dept: Optional[str] = None  # DISC, DES, MGT, DEV
    initials: Optional[str] = None
    manager_id: Optional[str] = None
    task_id: Optional[int] = None
    status: str = 'idle'  # active, complete, pending, working, idle
    created_at: Optional[str] = None
    last_active: Optional[str] = None

    def to_graph_agent(self) -> Dict[str, Any]:
        """Convert to Graph.html agent format."""
        return {
            'id': self.id,
            'name': self.name,
            'dept': self.dept or 'DEV',
            'initials': self.initials or self.name[:2].upper(),
            'status': self.status
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'dept': self.dept,
            'initials': self.initials,
            'manager_id': self.manager_id,
            'task_id': self.task_id,
            'status': self.status,
            'created_at': self.created_at,
            'last_active': self.last_active
        }


@dataclass
class Task:
    """Represents a work task."""
    id: Optional[int]
    component_id: str
    title: str
    manager_id: Optional[str] = None
    description: Optional[str] = None
    logic: Optional[str] = None
    status: str = 'pending'
    priority: int = 0
    assigned_agent: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'component_id': self.component_id,
            'manager_id': self.manager_id,
            'title': self.title,
            'description': self.description,
            'logic': self.logic,
            'status': self.status,
            'priority': self.priority,
            'assigned_agent': self.assigned_agent,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'completed_at': self.completed_at
        }


@dataclass
class Log:
    """Represents a log entry."""
    id: Optional[int]
    action: str
    message: str
    project_id: Optional[str] = None
    component_id: Optional[str] = None
    task_id: Optional[int] = None
    agent_id: Optional[str] = None
    level: str = 'info'  # debug, info, warn, error
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'component_id': self.component_id,
            'task_id': self.task_id,
            'agent_id': self.agent_id,
            'action': self.action,
            'message': self.message,
            'level': self.level,
            'timestamp': self.timestamp
        }


@dataclass
class GlobalTask:
    """Represents a project-level phase/task."""
    id: Optional[int]
    project_id: str
    text: str
    done: bool = False
    sort_order: int = 0

    def to_graph_task(self) -> Dict[str, Any]:
        """Convert to Graph.html globalTasks format."""
        return {
            'text': self.text,
            'done': self.done
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'text': self.text,
            'done': self.done,
            'sort_order': self.sort_order
        }
