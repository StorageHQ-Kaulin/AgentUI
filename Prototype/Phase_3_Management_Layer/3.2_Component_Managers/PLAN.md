# 3.2 Component Managers

## Objective

Create Component Manager agents that take a single component and break it down into specific, actionable tasks with clear acceptance criteria and dependencies.

## Files to Create

```
Visual/
├── agents/
│   ├── component_manager.py  # Component Manager agent
│   └── prompts/
│       └── component_manager.txt
```

## Key Responsibilities

1. **Task Decomposition**: Break component into 3-8 specific tasks
2. **Dependency Mapping**: Define task execution order
3. **Acceptance Criteria**: Define what "done" looks like for each task
4. **Agent Assignment**: Create Worker agents for tasks

## Implementation

### prompts/component_manager.txt

```
You are a Component Manager responsible for breaking down a component into specific implementation tasks.

INPUT:
- Component details (summary, requirements, risks)
- Component scope and boundaries
- Available inputs and expected outputs

OUTPUT:
A task breakdown with:
1. Specific, actionable tasks (3-8 tasks)
2. Clear acceptance criteria per task
3. Task dependencies
4. Estimated complexity

TASK DESIGN PRINCIPLES:
1. Single Responsibility: Each task does one thing
2. Testable: Clear pass/fail criteria
3. Right-Sized: Completable in 1-3 Claude Code sessions
4. Independent: Minimize cross-task dependencies

TASK STATUS OPTIONS:
- "pending": Not started
- "in_progress": Being worked on
- "blocked": Waiting on dependency
- "complete": Done and verified

OUTPUT FORMAT (JSON):
{
    "tasks": [
        {
            "id": "task_1",
            "title": "Short descriptive title",
            "description": "Detailed task description",
            "logic": "Implementation approach",
            "acceptance_criteria": [
                "Criterion 1 that can be verified",
                "Criterion 2"
            ],
            "dependencies": [],
            "estimated_complexity": "low|medium|high",
            "files_to_create": ["path/to/file.py"],
            "files_to_modify": ["existing/file.py"]
        }
    ],
    "task_order": ["task_1", "task_2", "task_3"],
    "notes": "Additional context for workers"
}
```

### component_manager.py

```python
"""
Component Manager Agent - Breaks components into tasks.
"""
from typing import Dict, Any, List
import uuid

from .base_agent import BaseAgent
from db import Database

class ComponentManagerAgent(BaseAgent):
    """
    Breaks a component into specific implementation tasks.

    Scope: Single component + its edges
    Inputs: Component from architecture
    Outputs: Task list with dependencies
    """

    def __init__(self, db: Database, manager_id: str, component_id: str):
        super().__init__(
            agent_id=manager_id,
            agent_type="component_manager",
            db=db
        )
        self.component_id = component_id
        self.manager_record = db.get_manager(manager_id)

    def get_scoped_context(self) -> Dict[str, Any]:
        """Manager sees only its component."""
        return {
            "role": "component_manager",
            "component_id": self.component_id,
            "access": ["own_component", "related_edges"],
            "restrictions": ["no_other_components", "no_other_tasks"]
        }

    def execute(self) -> Dict[str, Any]:
        """
        Break component into tasks.

        Returns:
            Task breakdown with dependencies
        """
        self.log('start', f'Breaking down component {self.component_id}')

        # Load component
        component = self.db.get_component(self.component_id)
        if not component:
            raise ValueError(f"Component {self.component_id} not found")

        # Get related edges (inputs to this component)
        project_id = self.manager_record.project_id
        edges = self.db.get_edges_for_component(self.component_id)

        # Build context
        context = self._build_context(component, edges)

        # Call Claude
        system_prompt = self.get_system_prompt()
        response = self.call_claude(
            prompt=context,
            system=system_prompt,
            expect_json=True
        )

        # Parse response
        breakdown = self.parse_json_response(response)

        # Validate and enhance
        breakdown = self._validate_breakdown(breakdown, component)

        # Save tasks to database
        self._save_tasks(breakdown['tasks'])

        # Update component status
        self.db.update_component(self.component_id, {
            'status': 'breakdown_complete',
            'subtasks': [{'title': t['title'], 'logic': t['logic']} for t in breakdown['tasks']]
        })

        self.log('complete', f'Created {len(breakdown["tasks"])} tasks')

        return breakdown

    def _build_context(self, component, edges: List) -> str:
        """Build prompt context from component data."""
        incoming = [e for e in edges if e.to_id == self.component_id]
        outgoing = [e for e in edges if e.from_id == self.component_id]

        context = f"""
COMPONENT TO BREAK DOWN:
ID: {component.id}
Label: {component.label}
Summary: {component.summary or 'No description'}
Problem: {component.problem or 'Not specified'}

SCOPE:
{chr(10).join('- ' + s for s in (component.scope or ['Not defined']))}

REQUIREMENTS:
{chr(10).join('- ' + r for r in (component.requirements or ['Not defined']))}

RISKS:
{chr(10).join('- ' + r for r in (component.risks or ['None identified']))}

INPUTS (from other components):
{chr(10).join('- ' + e.from_id + ': ' + (e.label or 'data') for e in incoming) or '- None'}

OUTPUTS (to other components):
{chr(10).join('- ' + e.to_id + ': ' + (e.label or 'data') for e in outgoing) or '- None'}

TASK:
Break this component into 3-8 specific implementation tasks.
Each task should be completable by a single agent.
Define clear acceptance criteria for each.
"""
        return context

    def _validate_breakdown(self, breakdown: Dict, component) -> Dict:
        """Ensure breakdown has all required fields."""
        if 'tasks' not in breakdown:
            breakdown['tasks'] = []

        # Validate each task
        for i, task in enumerate(breakdown['tasks']):
            task.setdefault('id', f"{self.component_id}_task_{i}")
            task.setdefault('title', f"Task {i+1}")
            task.setdefault('description', '')
            task.setdefault('logic', '')
            task.setdefault('acceptance_criteria', [])
            task.setdefault('dependencies', [])
            task.setdefault('estimated_complexity', 'medium')
            task.setdefault('files_to_create', [])
            task.setdefault('files_to_modify', [])
            task.setdefault('status', 'pending')

        # Generate task order if not provided
        if 'task_order' not in breakdown:
            breakdown['task_order'] = [t['id'] for t in breakdown['tasks']]

        return breakdown

    def _save_tasks(self, tasks: List[Dict]):
        """Save tasks to database."""
        for i, task in enumerate(tasks):
            self.db.create_task(
                component_id=self.component_id,
                manager_id=self.agent_id,
                title=task['title'],
                description=task.get('description', ''),
                logic=task.get('logic', ''),
                status='pending',
                priority=i
            )

    def assign_agent_to_task(self, task_id: int) -> str:
        """Create and assign a worker agent to a task."""
        agent_id = f"agent_{task_id}_{uuid.uuid4().hex[:6]}"

        # Create agent
        self.db.create_agent(
            id=agent_id,
            name=f"Worker {task_id}",
            dept="DEV",
            initials="WK",
            manager_id=self.agent_id,
            task_id=task_id,
            status='assigned'
        )

        # Update task
        self.db.update_task(task_id, {'assigned_agent': agent_id})

        self.log('assign', f'Assigned agent {agent_id} to task {task_id}')

        return agent_id

    def get_task_status(self) -> Dict[str, Any]:
        """Get status of all tasks for this component."""
        tasks = self.db.get_tasks_for_component(self.component_id)
        return {
            'component_id': self.component_id,
            'total_tasks': len(tasks),
            'completed': sum(1 for t in tasks if t.status == 'complete'),
            'in_progress': sum(1 for t in tasks if t.status == 'in_progress'),
            'blocked': sum(1 for t in tasks if t.status == 'blocked'),
            'pending': sum(1 for t in tasks if t.status == 'pending'),
            'tasks': [
                {
                    'id': t.id,
                    'title': t.title,
                    'status': t.status,
                    'assigned_agent': t.assigned_agent
                }
                for t in tasks
            ]
        }
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] ComponentManagerAgent loads single component
- [ ] Generates 3-8 tasks per component
- [ ] Tasks have clear titles and descriptions
- [ ] Tasks have acceptance criteria
- [ ] Task dependencies are defined
- [ ] Tasks saved to database
- [ ] Component subtasks updated
- [ ] Can assign worker agents to tasks
- [ ] Task status tracking works
- [ ] Works for simple components (3 tasks)
- [ ] Works for complex components (8 tasks)
- [ ] Handles components with external dependencies

## Tests Required

### test_component_manager.py

```python
import pytest
from unittest.mock import Mock, patch
from agents.component_manager import ComponentManagerAgent
from db import Database

class TestComponentManagerAgent:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / 'test.db'))

    @pytest.fixture
    def project_with_manager(self, db):
        """Project with manager and component."""
        db.create_project('proj1', 'Test')
        db.create_component('comp_api', 'proj1', 'API Layer',
            summary='REST API', requirements=['Authentication', 'Rate limiting'])
        db.create_manager('mgr_api', 'proj1', 'comp_api')
        return 'proj1', 'mgr_api', 'comp_api'

    @pytest.fixture
    def agent(self, db, project_with_manager):
        _, mgr_id, comp_id = project_with_manager
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test'}):
            with patch('anthropic.Anthropic'):
                return ComponentManagerAgent(db, mgr_id, comp_id)

    def test_creates_tasks(self, agent):
        """Breaks component into tasks."""
        mock_response = '''{
            "tasks": [
                {"id": "t1", "title": "Setup Express server", "logic": "npm init"},
                {"id": "t2", "title": "Add auth middleware", "logic": "JWT validation"},
                {"id": "t3", "title": "Add rate limiting", "logic": "Use express-rate-limit"}
            ],
            "task_order": ["t1", "t2", "t3"]
        }'''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            breakdown = agent.execute()

        assert len(breakdown['tasks']) == 3

    def test_tasks_have_acceptance_criteria(self, agent):
        """Tasks include acceptance criteria."""
        mock_response = '''{
            "tasks": [
                {
                    "id": "t1",
                    "title": "Setup server",
                    "acceptance_criteria": ["Server starts", "Responds to /health"]
                }
            ]
        }'''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            breakdown = agent.execute()

        task = breakdown['tasks'][0]
        assert 'acceptance_criteria' in task
        assert len(task['acceptance_criteria']) >= 1

    def test_saves_to_database(self, agent, db):
        """Tasks persist to database."""
        mock_response = '''{"tasks": [{"id": "t1", "title": "Task 1"}]}'''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            agent.execute()

        tasks = db.get_tasks_for_component('comp_api')
        assert len(tasks) >= 1

    def test_assigns_agent(self, agent, db):
        """Can assign worker to task."""
        mock_response = '''{"tasks": [{"id": "t1", "title": "Task 1"}]}'''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            agent.execute()

        tasks = db.get_tasks_for_component('comp_api')
        agent_id = agent.assign_agent_to_task(tasks[0].id)

        assert agent_id is not None
        task = db.get_task(tasks[0].id)
        assert task.assigned_agent == agent_id
```

---

*Status: Pending*
*Estimated Complexity: Medium*
*Dependencies: 3.1 General Manager*
