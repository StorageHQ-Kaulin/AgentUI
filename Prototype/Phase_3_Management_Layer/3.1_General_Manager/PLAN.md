# 3.1 General Manager Agent

## Objective

Create a General Manager agent that takes approved architecture and creates a project-wide work plan, then spawns Component Managers for each top-level component.

## Files to Create

```
Visual/
├── agents/
│   ├── general_manager.py    # General Manager agent
│   └── prompts/
│       └── general_manager.txt
```

## Key Responsibilities

1. **Work Plan Creation**: Analyze components and define execution order
2. **Manager Spawning**: Create a Manager agent per component
3. **Resource Allocation**: Decide parallelization strategy
4. **Progress Oversight**: Track overall project completion

## Implementation

### prompts/general_manager.txt

```
You are a General Manager responsible for project execution planning. Your job is to take an approved architecture and create a detailed work plan.

INPUT:
- Approved component tree
- Component dependencies (edges)
- Project requirements and constraints

OUTPUT:
A work plan that defines:
1. Execution order (respecting dependencies)
2. Parallelization opportunities
3. Manager assignments
4. Milestones and checkpoints

PLANNING PRINCIPLES:
1. Dependency Respect: Component B waits if it depends on A
2. Parallelism: Independent components can run simultaneously
3. Critical Path: Identify the longest dependency chain
4. Risk First: Tackle high-risk components early

OUTPUT FORMAT (JSON):
{
    "work_plan": {
        "phases": [
            {
                "phase_number": 1,
                "name": "Foundation",
                "components": ["comp_id_1", "comp_id_2"],
                "parallel": true,
                "description": "Why these components first"
            }
        ],
        "critical_path": ["comp_a", "comp_b", "comp_c"],
        "estimated_complexity": "low|medium|high",
        "risks": ["risk 1", "risk 2"]
    },
    "manager_assignments": [
        {
            "manager_id": "mgr_comp_1",
            "component_id": "comp_1",
            "priority": 1,
            "notes": "Start immediately"
        }
    ]
}
```

### general_manager.py

```python
"""
General Manager Agent - Project-level work planning and coordination.
"""
from typing import Dict, Any, List, Optional
import uuid

from .base_agent import BaseAgent
from db import Database

class GeneralManagerAgent(BaseAgent):
    """
    Creates work plans and spawns component managers.

    Scope: All components, approved design
    Inputs: Approved architecture from Architect
    Outputs: Work plan, Manager agents
    """

    def __init__(self, db: Database, project_id: str):
        super().__init__(
            agent_id=f"gm_{project_id}_{uuid.uuid4().hex[:6]}",
            agent_type="general_manager",
            db=db
        )
        self.project_id = project_id

    def get_scoped_context(self) -> Dict[str, Any]:
        """General Manager sees all components but not task details."""
        return {
            "role": "general_manager",
            "access": ["components", "edges", "project_info"],
            "restrictions": ["no_task_details", "no_agent_logs"]
        }

    def execute(self) -> Dict[str, Any]:
        """
        Create work plan and spawn managers.

        Returns:
            Work plan with manager assignments
        """
        self.log('start', f'Creating work plan for project {self.project_id}')

        # Load project data
        project = self.db.get_project(self.project_id)
        components = self.db.get_components(self.project_id)
        edges = self.db.get_edges(self.project_id)

        # Build context for Claude
        context = self._build_context(project, components, edges)

        # Call Claude for work plan
        system_prompt = self.get_system_prompt()
        response = self.call_claude(
            prompt=context,
            system=system_prompt,
            expect_json=True
        )

        # Parse response
        plan = self.parse_json_response(response)

        # Validate and enhance
        plan = self._validate_plan(plan, components)

        # Save work plan to project
        self.db.update_project(self.project_id, {
            'work_plan': plan.get('work_plan'),
            'phase': 'planning'
        })

        # Spawn managers
        managers = self._spawn_managers(plan.get('manager_assignments', []))
        plan['spawned_managers'] = managers

        # Update global tasks
        self.db.mark_global_task_done(self.project_id, "Phase 4")

        self.log('complete', f'Created work plan with {len(managers)} managers')

        return plan

    def _build_context(self, project, components: List, edges: List) -> str:
        """Build prompt context from project data."""
        # Filter to non-root components
        work_components = [c for c in components if c.type != 'root']

        context = f"""
PROJECT: {project.name}
Summary: {project.summary}

COMPONENTS TO PLAN ({len(work_components)}):
"""
        for comp in work_components:
            deps = [e.from_id for e in edges if e.to_id == comp.id]
            context += f"""
- {comp.id}: {comp.label}
  Summary: {comp.summary or 'No description'}
  Dependencies: {', '.join(deps) if deps else 'None'}
  Requirements: {', '.join(comp.requirements or [])}
  Risks: {', '.join(comp.risks or [])}
"""

        context += f"""
DEPENDENCIES ({len(edges)} edges):
"""
        for edge in edges:
            context += f"- {edge.from_id} -> {edge.to_id} ({edge.type})\n"

        context += """
TASK:
Create a work plan that:
1. Respects all dependencies
2. Maximizes parallelism where possible
3. Addresses high-risk items early
4. Assigns a manager to each component
"""
        return context

    def _validate_plan(self, plan: Dict, components: List) -> Dict:
        """Ensure plan covers all components."""
        if 'work_plan' not in plan:
            plan['work_plan'] = {'phases': [], 'critical_path': [], 'risks': []}

        if 'manager_assignments' not in plan:
            plan['manager_assignments'] = []

        # Ensure all components have a manager
        planned_components = {ma['component_id'] for ma in plan['manager_assignments']}
        work_components = [c for c in components if c.type != 'root']

        for comp in work_components:
            if comp.id not in planned_components:
                plan['manager_assignments'].append({
                    'manager_id': f'mgr_{comp.id}',
                    'component_id': comp.id,
                    'priority': 99,  # Low priority for missed ones
                    'notes': 'Auto-assigned'
                })

        return plan

    def _spawn_managers(self, assignments: List[Dict]) -> List[Dict]:
        """Create Manager entries in database."""
        spawned = []

        for assignment in assignments:
            manager_id = assignment.get('manager_id', f"mgr_{uuid.uuid4().hex[:6]}")
            component_id = assignment['component_id']

            # Create manager record
            self.db.create_manager(
                id=manager_id,
                project_id=self.project_id,
                component_id=component_id,
                status='active',
                created_by=self.agent_id
            )

            # Create agent record for the manager
            self.db.create_agent(
                id=manager_id,
                name=f"Manager: {component_id}",
                dept="MGT",
                initials="MG",
                status='active'
            )

            spawned.append({
                'manager_id': manager_id,
                'component_id': component_id,
                'status': 'spawned'
            })

            self.log('spawn_manager', f'Spawned manager {manager_id} for {component_id}')

        return spawned

    def get_work_plan_summary(self) -> Dict[str, Any]:
        """Get current work plan status."""
        project = self.db.get_project(self.project_id)
        managers = self.db.get_managers(self.project_id)

        return {
            'project_id': self.project_id,
            'phase': project.phase,
            'work_plan': project.work_plan,
            'managers': [
                {
                    'id': m.id,
                    'component_id': m.component_id,
                    'status': m.status
                }
                for m in managers
            ]
        }
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] GeneralManagerAgent loads project architecture
- [ ] Work plan respects component dependencies
- [ ] Work plan identifies parallelization opportunities
- [ ] Critical path is calculated correctly
- [ ] Manager spawned for each component
- [ ] Managers stored in database
- [ ] Project phase updated to 'planning'
- [ ] Global task marked complete
- [ ] Works for linear dependency chains
- [ ] Works for parallel-capable architectures
- [ ] Handles edge cases (single component, no dependencies)

## Tests Required

### test_general_manager.py

```python
import pytest
from unittest.mock import Mock, patch
from agents.general_manager import GeneralManagerAgent
from db import Database

class TestGeneralManagerAgent:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / 'test.db'))

    @pytest.fixture
    def project_with_arch(self, db):
        """Project with approved architecture."""
        db.create_project('proj1', 'Test Project', phase='design')
        db.create_component('ROOT', 'proj1', 'Test', type='root')
        db.create_component('comp_a', 'proj1', 'Component A')
        db.create_component('comp_b', 'proj1', 'Component B')
        db.create_component('comp_c', 'proj1', 'Component C')
        # B depends on A, C is independent
        db.create_edge('proj1', 'ROOT', 'comp_a', 'init', 'data')
        db.create_edge('proj1', 'comp_a', 'comp_b', 'depends', 'data')
        db.create_edge('proj1', 'ROOT', 'comp_c', 'init', 'data')
        return 'proj1'

    @pytest.fixture
    def agent(self, db, project_with_arch):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test'}):
            with patch('anthropic.Anthropic'):
                return GeneralManagerAgent(db, project_with_arch)

    def test_creates_work_plan(self, agent):
        """Creates work plan with phases."""
        mock_response = '''{
            "work_plan": {
                "phases": [
                    {"phase_number": 1, "components": ["comp_a", "comp_c"], "parallel": true},
                    {"phase_number": 2, "components": ["comp_b"], "parallel": false}
                ],
                "critical_path": ["comp_a", "comp_b"]
            },
            "manager_assignments": [
                {"manager_id": "mgr_a", "component_id": "comp_a"},
                {"manager_id": "mgr_b", "component_id": "comp_b"},
                {"manager_id": "mgr_c", "component_id": "comp_c"}
            ]
        }'''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            plan = agent.execute()

        assert 'work_plan' in plan
        assert len(plan['work_plan']['phases']) == 2

    def test_spawns_managers(self, agent, db):
        """Spawns manager for each component."""
        mock_response = '''{
            "work_plan": {"phases": []},
            "manager_assignments": [
                {"manager_id": "mgr_a", "component_id": "comp_a"}
            ]
        }'''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            plan = agent.execute()

        managers = db.get_managers('proj1')
        assert len(managers) >= 1

    def test_respects_dependencies(self, agent):
        """Work plan respects dependency order."""
        mock_response = '''{
            "work_plan": {
                "phases": [
                    {"phase_number": 1, "components": ["comp_a"]},
                    {"phase_number": 2, "components": ["comp_b"]}
                ],
                "critical_path": ["comp_a", "comp_b"]
            },
            "manager_assignments": []
        }'''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            plan = agent.execute()

        # comp_b should come after comp_a
        phases = plan['work_plan']['phases']
        comp_a_phase = next(p['phase_number'] for p in phases if 'comp_a' in p['components'])
        comp_b_phase = next(p['phase_number'] for p in phases if 'comp_b' in p['components'])
        assert comp_a_phase < comp_b_phase
```

---

*Status: Pending*
*Estimated Complexity: High*
*Dependencies: Phase 2 Complete*
