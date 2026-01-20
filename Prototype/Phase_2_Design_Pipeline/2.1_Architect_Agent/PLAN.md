# 2.1 Architect Agent

## Objective

Create an Architect agent that takes the Interviewer's project brief and generates a detailed system architecture with components, dependencies, and data flows.

## Files to Create

```
Visual/
├── agents/
│   ├── architect.py         # Architect agent class
│   └── prompts/
│       └── architect.txt    # System prompt for architecture
```

## Key Responsibilities

1. **Component Decomposition**: Break project into logical modules
2. **Dependency Mapping**: Identify relationships between components
3. **Layout Generation**: Position nodes for Graph.html rendering
4. **Metric Definition**: Define success criteria per component
5. **Risk Assessment**: Identify technical risks per component

## Implementation

### prompts/architect.txt

```
You are an expert software architect. Your job is to take a project brief and design a detailed system architecture.

INPUT: A project brief with:
- Title, summary, problem statement
- Initial components identified
- High-level requirements and risks

OUTPUT: A detailed architecture with:
- Refined component hierarchy (3-10 components)
- Dependencies between components
- Data flow definitions
- Metrics and test cases per component

ARCHITECTURE PRINCIPLES:
1. Single Responsibility: Each component does one thing well
2. Loose Coupling: Minimize dependencies between components
3. High Cohesion: Related functionality grouped together
4. Testability: Each component can be tested independently

COMPONENT STRUCTURE:
For each component, define:
- id: Unique identifier (e.g., "comp_auth")
- label: Human-readable name
- type: "node" (or "root" for project root)
- summary: What this component does (1-2 sentences)
- problem: What issue it solves
- goals: List of specific objectives
- scope: What's included/excluded
- requirements: Functional requirements
- risks: What could go wrong
- inputs: What data/signals it receives
- outputs: What data/signals it produces
- metrics: Measurable success criteria with weights
- testCases: Test scenarios with weights

EDGE DEFINITIONS:
For dependencies, specify:
- from: Source component ID
- to: Target component ID
- label: Description of the connection
- type: One of:
  - "data": Data flows from source to target
  - "api": Source calls target's API
  - "auth": Authentication/authorization dependency
  - "schema": Schema/type definition dependency
  - "log": Logging/monitoring connection

LAYOUT RULES:
- Root node at top (y=50)
- First level at y=200
- Each subsequent level +150 y
- Horizontal spread based on siblings
- Center main flow, branch utilities to sides

OUTPUT FORMAT (JSON):
{
    "components": [
        {
            "id": "string",
            "label": "string",
            "type": "root|node",
            "status": "pending",
            "x": number,
            "y": number,
            "summary": "string",
            "problem": "string",
            "goals": ["string"],
            "scope": ["string"],
            "requirements": ["string"],
            "risks": ["string"],
            "inputs": ["string"],
            "outputs": ["string"],
            "files": [],
            "subtasks": [],
            "metrics": [{"req": "string", "value": "TBD", "status": "pending", "weight": number}],
            "testCases": [{"name": "string", "status": "pending", "weight": number}]
        }
    ],
    "edges": [
        {"from": "string", "to": "string", "label": "string", "type": "data|api|auth|schema|log"}
    ],
    "architecture_notes": "string describing key decisions"
}
```

### architect.py

```python
"""
Architect Agent - Phase 2 of the orchestration pipeline.
Designs system architecture from project briefs.
"""
from typing import Dict, Any, Optional, List
import uuid
import math

from .base_agent import BaseAgent
from db import Database

class ArchitectAgent(BaseAgent):
    """
    Designs system architecture from project briefs.

    Scope: Project brief + optionally codebase analysis
    Inputs: Interviewer output (project brief)
    Outputs: Component tree with edges
    """

    def __init__(self, db: Database):
        super().__init__(
            agent_id=f"architect_{uuid.uuid4().hex[:8]}",
            agent_type="architect",
            db=db
        )

    def get_scoped_context(self) -> Dict[str, Any]:
        """Architect sees project brief and codebase analysis only."""
        return {
            "role": "architect",
            "access": ["project_brief", "codebase_analysis"],
            "restrictions": ["no_execution", "no_other_agents_state"]
        }

    def execute(
        self,
        project_id: str,
        codebase_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Design architecture for a project.

        Args:
            project_id: The project to design architecture for
            codebase_analysis: Optional analysis of existing codebase

        Returns:
            Architecture with components and edges
        """
        self.log('start', f'Designing architecture for project {project_id}')

        # Load project brief
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        existing_components = self.db.get_components(project_id)
        existing_edges = self.db.get_edges(project_id)

        # Build context for Claude
        context = self._build_context(project, existing_components, existing_edges, codebase_analysis)

        # Call Claude
        system_prompt = self.get_system_prompt()
        response = self.call_claude(
            prompt=context,
            system=system_prompt,
            expect_json=True
        )

        # Parse response
        architecture = self.parse_json_response(response)

        # Validate and enhance
        architecture = self._validate_architecture(architecture, project)

        # Calculate layout positions
        architecture = self._calculate_layout(architecture)

        # Save to database
        self._save_to_database(project_id, architecture)

        # Update project phase
        self.db.update_project(project_id, {'phase': 'design'})

        self.log('complete', f'Generated {len(architecture["components"])} components')

        return architecture

    def _build_context(
        self,
        project,
        existing_components: List,
        existing_edges: List,
        codebase_analysis: Optional[Dict]
    ) -> str:
        """Build prompt context from available data."""
        context = f"""
PROJECT BRIEF:
Title: {project.name}
Summary: {project.summary or 'Not specified'}
Problem: {project.problem or 'Not specified'}
Phase: {project.phase}

EXISTING COMPONENTS ({len(existing_components)}):
"""
        for comp in existing_components:
            context += f"- {comp.label}: {comp.summary or 'No description'}\n"

        context += f"\nEXISTING EDGES ({len(existing_edges)}):\n"
        for edge in existing_edges:
            context += f"- {edge.from_id} -> {edge.to_id} ({edge.type}): {edge.label}\n"

        if codebase_analysis:
            context += f"\nCODEBASE ANALYSIS:\n"
            context += f"Languages: {', '.join(codebase_analysis.get('languages', []))}\n"
            context += f"File Count: {codebase_analysis.get('file_count', 0)}\n"
            context += f"Dependencies: {', '.join(codebase_analysis.get('dependencies', []))}\n"
            context += f"Entry Points: {', '.join(codebase_analysis.get('entry_points', []))}\n"

        context += """
TASK:
Based on this information, create a detailed system architecture.
Refine the components, add missing ones, and define clear dependencies.
"""
        return context

    def _validate_architecture(self, arch: Dict, project) -> Dict:
        """Ensure architecture has all required fields."""
        # Ensure components list
        if 'components' not in arch:
            arch['components'] = []

        # Ensure edges list
        if 'edges' not in arch:
            arch['edges'] = []

        # Validate each component
        for comp in arch['components']:
            comp.setdefault('id', f"comp_{uuid.uuid4().hex[:6]}")
            comp.setdefault('label', 'Unnamed Component')
            comp.setdefault('type', 'node')
            comp.setdefault('status', 'pending')
            comp.setdefault('summary', '')
            comp.setdefault('problem', '')
            comp.setdefault('goals', [])
            comp.setdefault('scope', [])
            comp.setdefault('requirements', [])
            comp.setdefault('risks', [])
            comp.setdefault('inputs', [])
            comp.setdefault('outputs', [])
            comp.setdefault('files', [])
            comp.setdefault('subtasks', [])
            comp.setdefault('metrics', [])
            comp.setdefault('testCases', [])

        # Ensure root node exists
        has_root = any(c['type'] == 'root' for c in arch['components'])
        if not has_root:
            root = {
                'id': 'ROOT',
                'label': project.name,
                'type': 'root',
                'status': 'active',
                'summary': project.summary or '',
                'problem': project.problem or '',
                'goals': [],
                'scope': [],
                'requirements': [],
                'risks': [],
                'inputs': ['User Request'],
                'outputs': ['Completed System'],
                'files': [],
                'subtasks': [],
                'metrics': [],
                'testCases': []
            }
            arch['components'].insert(0, root)

        return arch

    def _calculate_layout(self, arch: Dict) -> Dict:
        """Calculate x,y positions for all components."""
        components = arch['components']

        # Build adjacency for level calculation
        children = {}  # parent_id -> [child_ids]
        for edge in arch.get('edges', []):
            parent = edge['from']
            child = edge['to']
            if parent not in children:
                children[parent] = []
            children[parent].append(child)

        # Find root
        root_id = None
        for comp in components:
            if comp['type'] == 'root':
                root_id = comp['id']
                break

        if not root_id and components:
            root_id = components[0]['id']

        # BFS to assign levels
        levels = {root_id: 0}
        queue = [root_id]
        while queue:
            current = queue.pop(0)
            current_level = levels[current]
            for child in children.get(current, []):
                if child not in levels:
                    levels[child] = current_level + 1
                    queue.append(child)

        # Group by level
        level_groups = {}
        for comp in components:
            level = levels.get(comp['id'], 0)
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(comp)

        # Assign positions
        for level, comps in level_groups.items():
            y = 50 + (level * 150)
            width = len(comps) * 200
            start_x = 500 - (width / 2) + 100

            for i, comp in enumerate(comps):
                comp['x'] = int(start_x + (i * 200))
                comp['y'] = y

        return arch

    def _save_to_database(self, project_id: str, architecture: Dict):
        """Save architecture to database, replacing existing."""
        # Delete existing components and edges
        self.db.delete_components(project_id)
        self.db.delete_edges(project_id)

        # Save new components
        for comp in architecture['components']:
            self.db.create_component(
                id=comp['id'],
                project_id=project_id,
                label=comp['label'],
                type=comp['type'],
                status=comp['status'],
                x=comp.get('x', 0),
                y=comp.get('y', 0),
                summary=comp.get('summary'),
                problem=comp.get('problem'),
                goals=comp.get('goals', []),
                scope=comp.get('scope', []),
                requirements=comp.get('requirements', []),
                risks=comp.get('risks', []),
                inputs=comp.get('inputs', []),
                outputs=comp.get('outputs', []),
                files=comp.get('files', []),
                subtasks=comp.get('subtasks', [])
            )

            # Save metrics for this component
            for metric in comp.get('metrics', []):
                self.db.create_metric(
                    component_id=comp['id'],
                    requirement=metric.get('req', ''),
                    value=metric.get('value'),
                    status=metric.get('status', 'pending'),
                    weight=metric.get('weight', 1.0)
                )

            # Save test cases for this component
            for tc in comp.get('testCases', []):
                self.db.create_test_case(
                    component_id=comp['id'],
                    name=tc.get('name', ''),
                    status=tc.get('status', 'pending'),
                    value=tc.get('value'),
                    weight=tc.get('weight', 1.0)
                )

        # Save new edges
        for edge in architecture['edges']:
            self.db.create_edge(
                project_id=project_id,
                from_id=edge['from'],
                to_id=edge['to'],
                label=edge.get('label', ''),
                type=edge.get('type', 'data')
            )
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] ArchitectAgent class extends BaseAgent correctly
- [ ] Can load project brief from database
- [ ] Generates refined component list (3-10 components)
- [ ] Components have all Graph.html fields populated
- [ ] Edges correctly link components
- [ ] Layout positions are calculated correctly
- [ ] Metrics and test cases defined per component
- [ ] Architecture saved to database
- [ ] Dashboard renders generated architecture
- [ ] Works for simple projects (3 components)
- [ ] Works for complex projects (8+ components)
- [ ] Integrates codebase analysis when provided

## Tests Required

### test_architect.py

```python
import pytest
from unittest.mock import Mock, patch
from agents.architect import ArchitectAgent
from agents.interviewer import InterviewerAgent
from db import Database

class TestArchitectAgent:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / 'test.db'))

    @pytest.fixture
    def agent(self, db):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            with patch('anthropic.Anthropic'):
                return ArchitectAgent(db)

    @pytest.fixture
    def project_with_brief(self, db, agent):
        """Create a project with interviewer brief."""
        db.create_project('test_proj', 'Test Project',
            summary='A test project', problem='Testing')
        db.create_component('ROOT', 'test_proj', 'Test Project', type='root')
        db.create_component('comp_1', 'test_proj', 'Component 1')
        return 'test_proj'

    def test_loads_project_brief(self, agent, project_with_brief):
        """Can load existing project data"""
        mock_response = '''{"components": [], "edges": []}'''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            arch = agent.execute(project_with_brief)
        # Should not raise, project loaded

    def test_generates_components(self, agent, project_with_brief):
        """Generates detailed component list"""
        mock_response = '''
        {
            "components": [
                {"id": "api", "label": "API Layer", "type": "node"},
                {"id": "db", "label": "Database", "type": "node"},
                {"id": "auth", "label": "Auth", "type": "node"}
            ],
            "edges": [
                {"from": "api", "to": "db", "type": "data"},
                {"from": "api", "to": "auth", "type": "auth"}
            ]
        }
        '''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            arch = agent.execute(project_with_brief)

        assert len(arch['components']) >= 3

    def test_calculates_layout(self, agent, project_with_brief):
        """Positions are calculated for rendering"""
        mock_response = '''
        {
            "components": [
                {"id": "c1", "label": "C1", "type": "node"},
                {"id": "c2", "label": "C2", "type": "node"}
            ],
            "edges": [{"from": "ROOT", "to": "c1", "type": "data"}]
        }
        '''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            arch = agent.execute(project_with_brief)

        for comp in arch['components']:
            assert 'x' in comp
            assert 'y' in comp
            assert isinstance(comp['x'], int)
            assert isinstance(comp['y'], int)

    def test_saves_to_database(self, agent, db, project_with_brief):
        """Architecture persists to database"""
        mock_response = '''
        {
            "components": [
                {"id": "new_comp", "label": "New Component", "type": "node"}
            ],
            "edges": []
        }
        '''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            agent.execute(project_with_brief)

        comps = db.get_components(project_with_brief)
        assert any(c.id == 'new_comp' for c in comps)
```

---

*Status: Pending*
*Estimated Complexity: High*
*Dependencies: 1.1, 1.2, 1.3 (Phase 1 Complete)*
