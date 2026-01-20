# 3.3 Task Schema

## Objective

Define the complete task data structure and lifecycle, ensuring tasks have all information needed for Worker agents to execute them successfully.

## Files to Create/Update

```
Visual/
├── db/
│   └── models.py             # Add Task model
├── schemas/
│   ├── __init__.py
│   └── task.py               # Task schema definition
```

## Task Lifecycle

```
                    ┌─────────┐
                    │ PENDING │
                    └────┬────┘
                         │ Agent assigned
                         ▼
                    ┌─────────────┐
              ┌─────│ IN_PROGRESS │─────┐
              │     └──────┬──────┘     │
              │            │            │
         blocked      completed     failed
              │            │            │
              ▼            ▼            ▼
         ┌─────────┐ ┌──────────┐ ┌────────┐
         │ BLOCKED │ │ COMPLETE │ │ FAILED │
         └────┬────┘ └──────────┘ └───┬────┘
              │                       │
              │ dependency resolved   │ retry
              │                       │
              └───────────────────────┘
```

## Task Schema Definition

### schemas/task.py

```python
"""
Task Schema - Complete task data structure for agent execution.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    FAILED = "failed"

class TaskPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3

@dataclass
class AcceptanceCriterion:
    """Single acceptance criterion for a task."""
    description: str
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None

@dataclass
class FileReference:
    """Reference to a file involved in the task."""
    path: str
    action: str  # "create", "modify", "read"
    description: Optional[str] = None

@dataclass
class TaskDependency:
    """Dependency on another task."""
    task_id: str
    type: str = "completion"  # "completion", "partial", "data"
    satisfied: bool = False

@dataclass
class TaskContext:
    """Scoped context for agent execution."""
    component_summary: str
    component_requirements: List[str]
    inputs: List[str]
    expected_outputs: List[str]
    related_files: List[str]
    previous_task_outputs: Optional[Dict] = None

@dataclass
class Task:
    """Complete task structure for agent execution."""
    # Identity
    id: str
    component_id: str
    manager_id: str

    # Description
    title: str
    description: str
    logic: str  # Implementation approach

    # Status
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM

    # Assignment
    assigned_agent: Optional[str] = None
    assigned_at: Optional[str] = None

    # Dependencies
    dependencies: List[TaskDependency] = field(default_factory=list)

    # Acceptance
    acceptance_criteria: List[AcceptanceCriterion] = field(default_factory=list)

    # Files
    files_to_create: List[FileReference] = field(default_factory=list)
    files_to_modify: List[FileReference] = field(default_factory=list)
    files_to_read: List[FileReference] = field(default_factory=list)

    # Execution
    context: Optional[TaskContext] = None
    estimated_complexity: str = "medium"
    max_iterations: int = 10
    timeout_minutes: int = 30

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Results
    result: Optional[Dict] = None
    error: Optional[str] = None
    iterations_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'component_id': self.component_id,
            'manager_id': self.manager_id,
            'title': self.title,
            'description': self.description,
            'logic': self.logic,
            'status': self.status.value,
            'priority': self.priority.value,
            'assigned_agent': self.assigned_agent,
            'dependencies': [
                {'task_id': d.task_id, 'type': d.type, 'satisfied': d.satisfied}
                for d in self.dependencies
            ],
            'acceptance_criteria': [
                {'description': ac.description, 'verified': ac.verified}
                for ac in self.acceptance_criteria
            ],
            'files_to_create': [
                {'path': f.path, 'action': f.action}
                for f in self.files_to_create
            ],
            'files_to_modify': [
                {'path': f.path, 'action': f.action}
                for f in self.files_to_modify
            ],
            'estimated_complexity': self.estimated_complexity,
            'created_at': self.created_at,
            'completed_at': self.completed_at
        }

    def to_agent_prompt(self) -> str:
        """Generate prompt section for agent execution."""
        prompt = f"""
TASK: {self.title}
ID: {self.id}

DESCRIPTION:
{self.description}

IMPLEMENTATION APPROACH:
{self.logic}

ACCEPTANCE CRITERIA:
"""
        for i, ac in enumerate(self.acceptance_criteria, 1):
            status = "✓" if ac.verified else "○"
            prompt += f"{i}. [{status}] {ac.description}\n"

        prompt += "\nFILES TO CREATE:\n"
        for f in self.files_to_create:
            prompt += f"- {f.path}\n"

        prompt += "\nFILES TO MODIFY:\n"
        for f in self.files_to_modify:
            prompt += f"- {f.path}\n"

        if self.context:
            prompt += f"""
CONTEXT:
Component: {self.context.component_summary}
Inputs: {', '.join(self.context.inputs)}
Expected Outputs: {', '.join(self.context.expected_outputs)}
"""

        return prompt

    def can_start(self) -> bool:
        """Check if all dependencies are satisfied."""
        return all(d.satisfied for d in self.dependencies)

    def is_complete(self) -> bool:
        """Check if all acceptance criteria verified."""
        return all(ac.verified for ac in self.acceptance_criteria)

    def mark_criterion_verified(self, index: int, agent_id: str):
        """Mark an acceptance criterion as verified."""
        if 0 <= index < len(self.acceptance_criteria):
            self.acceptance_criteria[index].verified = True
            self.acceptance_criteria[index].verified_by = agent_id
            self.acceptance_criteria[index].verified_at = datetime.now().isoformat()

            if self.is_complete():
                self.status = TaskStatus.COMPLETE
                self.completed_at = datetime.now().isoformat()
```

## Database Updates

### Add to db/models.py

```python
@dataclass
class TaskRecord:
    """Database record for a task."""
    id: int
    component_id: str
    manager_id: str
    title: str
    description: Optional[str] = None
    logic: Optional[str] = None
    status: str = 'pending'
    priority: int = 2
    assigned_agent: Optional[str] = None
    dependencies: str = '[]'  # JSON string
    acceptance_criteria: str = '[]'  # JSON string
    files_to_create: str = '[]'  # JSON string
    files_to_modify: str = '[]'  # JSON string
    estimated_complexity: str = 'medium'
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None  # JSON string
    error: Optional[str] = None
    iterations_used: int = 0

    def to_task(self) -> 'Task':
        """Convert database record to Task object."""
        import json
        from schemas.task import (
            Task, TaskStatus, TaskPriority,
            AcceptanceCriterion, FileReference, TaskDependency
        )

        return Task(
            id=str(self.id),
            component_id=self.component_id,
            manager_id=self.manager_id,
            title=self.title,
            description=self.description or '',
            logic=self.logic or '',
            status=TaskStatus(self.status),
            priority=TaskPriority(self.priority),
            assigned_agent=self.assigned_agent,
            dependencies=[
                TaskDependency(**d) for d in json.loads(self.dependencies or '[]')
            ],
            acceptance_criteria=[
                AcceptanceCriterion(**ac) for ac in json.loads(self.acceptance_criteria or '[]')
            ],
            files_to_create=[
                FileReference(**f) for f in json.loads(self.files_to_create or '[]')
            ],
            files_to_modify=[
                FileReference(**f) for f in json.loads(self.files_to_modify or '[]')
            ],
            estimated_complexity=self.estimated_complexity,
            created_at=self.created_at or '',
            completed_at=self.completed_at
        )
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] Task dataclass defined with all fields
- [ ] TaskStatus enum covers all states
- [ ] TaskPriority enum defined
- [ ] AcceptanceCriterion supports verification tracking
- [ ] FileReference tracks file operations
- [ ] TaskDependency tracks dependency satisfaction
- [ ] TaskContext provides scoped information
- [ ] `to_dict()` serializes for database
- [ ] `to_agent_prompt()` generates execution prompt
- [ ] `can_start()` checks dependencies
- [ ] `is_complete()` checks acceptance criteria
- [ ] Database model matches schema
- [ ] Round-trip (save/load) preserves all data

## Tests Required

### test_task_schema.py

```python
import pytest
from schemas.task import (
    Task, TaskStatus, TaskPriority,
    AcceptanceCriterion, FileReference, TaskDependency, TaskContext
)

class TestTaskSchema:
    def test_task_creation(self):
        """Task creates with defaults."""
        task = Task(
            id='task_1',
            component_id='comp_1',
            manager_id='mgr_1',
            title='Test Task',
            description='A test',
            logic='Do the thing'
        )
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM

    def test_can_start_no_deps(self):
        """Task with no dependencies can start."""
        task = Task(id='t1', component_id='c1', manager_id='m1',
                    title='T', description='D', logic='L')
        assert task.can_start() == True

    def test_can_start_with_deps(self):
        """Task blocked by unsatisfied dependency."""
        task = Task(
            id='t1', component_id='c1', manager_id='m1',
            title='T', description='D', logic='L',
            dependencies=[TaskDependency(task_id='t0', satisfied=False)]
        )
        assert task.can_start() == False

        task.dependencies[0].satisfied = True
        assert task.can_start() == True

    def test_is_complete(self):
        """Completion requires all criteria verified."""
        task = Task(
            id='t1', component_id='c1', manager_id='m1',
            title='T', description='D', logic='L',
            acceptance_criteria=[
                AcceptanceCriterion(description='Criterion 1'),
                AcceptanceCriterion(description='Criterion 2')
            ]
        )
        assert task.is_complete() == False

        task.mark_criterion_verified(0, 'agent_1')
        assert task.is_complete() == False

        task.mark_criterion_verified(1, 'agent_1')
        assert task.is_complete() == True

    def test_to_dict_roundtrip(self):
        """Serialization preserves data."""
        task = Task(
            id='t1', component_id='c1', manager_id='m1',
            title='Test', description='Desc', logic='Logic',
            acceptance_criteria=[
                AcceptanceCriterion(description='AC1')
            ],
            files_to_create=[
                FileReference(path='src/new.py', action='create')
            ]
        )
        data = task.to_dict()

        assert data['title'] == 'Test'
        assert len(data['acceptance_criteria']) == 1
        assert len(data['files_to_create']) == 1

    def test_to_agent_prompt(self):
        """Generates valid agent prompt."""
        task = Task(
            id='t1', component_id='c1', manager_id='m1',
            title='Implement Login',
            description='Create login endpoint',
            logic='Use JWT',
            acceptance_criteria=[
                AcceptanceCriterion(description='Returns token'),
                AcceptanceCriterion(description='Validates password')
            ],
            files_to_create=[FileReference(path='auth.py', action='create')]
        )
        prompt = task.to_agent_prompt()

        assert 'Implement Login' in prompt
        assert 'Returns token' in prompt
        assert 'auth.py' in prompt
```

---

*Status: Pending*
*Estimated Complexity: Low*
*Dependencies: None (data structure definition)*
