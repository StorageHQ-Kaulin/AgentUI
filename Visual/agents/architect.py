"""
Architect Agent - Phase 2 of the orchestration pipeline.
Designs detailed system architecture from project briefs.
"""
import os
import sys
import uuid
from typing import Dict, Any, Optional, List

from .base_agent import BaseAgent, AgentConfig, MODELS

# Add parent directory to path for db import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import Database


class ArchitectAgent(BaseAgent):
    """
    Designs system architecture from project briefs.

    Scope: Project brief + optionally codebase analysis
    Inputs: Interviewer output (project brief)
    Outputs: Detailed component tree with edges, metrics, test cases
    """

    def __init__(self, db: Database, use_powerful_model: bool = False):
        """
        Initialize the architect agent.

        Args:
            db: Database instance for persistence
            use_powerful_model: If True, use the most powerful model for complex designs
        """
        config = AgentConfig(
            model=MODELS["balanced"] if not use_powerful_model else MODELS["powerful"],
            max_tokens=8192,  # Architecture needs more tokens
            temperature=0.5   # More deterministic for structured output
        )
        super().__init__(
            agent_id=f"architect_{uuid.uuid4().hex[:8]}",
            agent_type="architect",
            db=db,
            config=config
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

        try:
            response = self.call_claude(
                prompt=context,
                system=system_prompt,
                expect_json=True
            )

            # Parse response
            architecture = self.parse_json_response(response)

        except Exception as e:
            self.log('error', f'Failed to get Claude response: {e}')
            # Return fallback architecture on failure
            architecture = self._fallback_architecture(project)

        # Validate and enhance
        architecture = self._validate_architecture(architecture, project)

        # Calculate layout positions
        architecture = self._calculate_layout(architecture)

        # Save to database
        self._save_to_database(project_id, architecture)

        # Update project phase
        self.db.update_project(project_id, {'phase': 'design'})

        # Mark global task as done
        self.db.mark_global_task_done(project_id, "Phase 2")

        # Create architect agent record
        self.db.create_agent(
            id=self.agent_id,
            name="Architect",
            dept="DES",
            initials="AR",
            status="complete"
        )

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
        context = f"""PROJECT BRIEF:
Title: {project.name}
Summary: {project.summary or 'Not specified'}
Problem: {project.problem or 'Not specified'}
Phase: {project.phase}

EXISTING COMPONENTS ({len(existing_components)}):
"""
        for comp in existing_components:
            if comp.type != 'root':
                context += f"- {comp.label}: {comp.summary or 'No description'}\n"
                if comp.inputs:
                    context += f"  Inputs: {', '.join(comp.inputs)}\n"
                if comp.outputs:
                    context += f"  Outputs: {', '.join(comp.outputs)}\n"
                if comp.requirements:
                    context += f"  Requirements: {', '.join(comp.requirements[:3])}\n"

        if existing_edges:
            context += f"\nEXISTING EDGES ({len(existing_edges)}):\n"
            for edge in existing_edges:
                context += f"- {edge.from_id} -> {edge.to_id} ({edge.type}): {edge.label}\n"

        if codebase_analysis:
            context += f"\nCODEBASE ANALYSIS:\n"
            context += f"Languages: {', '.join(codebase_analysis.get('languages', []))}\n"
            context += f"File Count: {codebase_analysis.get('file_count', 0)}\n"
            if codebase_analysis.get('dependencies'):
                context += f"Dependencies: {', '.join(codebase_analysis.get('dependencies', [])[:10])}\n"
            if codebase_analysis.get('entry_points'):
                context += f"Entry Points: {', '.join(codebase_analysis.get('entry_points', []))}\n"
            if codebase_analysis.get('components'):
                context += f"Detected Components: {len(codebase_analysis.get('components', []))}\n"

        context += """
TASK:
Based on this information, create a detailed system architecture.
Refine the components, add missing ones, and define clear dependencies.
Ensure each component has metrics and test cases defined.
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

        # Generate unique prefix for this architecture
        import hashlib
        arch_hash = hashlib.md5(str(project.summary or project.name).encode()).hexdigest()[:6]

        # Validate each component
        for i, comp in enumerate(arch['components']):
            # Ensure unique ID
            if not comp.get('id') or comp['id'].startswith('comp_'):
                comp['id'] = f"a_{arch_hash}_{i}"
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

            # Ensure metrics have proper structure
            for metric in comp.get('metrics', []):
                metric.setdefault('req', 'Requirement')
                metric.setdefault('value', 'TBD')
                metric.setdefault('status', 'pending')
                metric.setdefault('weight', 1.0)

            # Ensure test cases have proper structure
            for tc in comp.get('testCases', []):
                tc.setdefault('name', 'Test Case')
                tc.setdefault('status', 'pending')
                tc.setdefault('weight', 1.0)

        # Ensure root node exists
        has_root = any(c['type'] == 'root' for c in arch['components'])
        if not has_root:
            root = {
                'id': f'ROOT_{arch_hash}',
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

            # Add edges from root to first-level components
            for comp in arch['components'][1:]:
                # Check if component already has an incoming edge
                has_incoming = any(e['to'] == comp['id'] for e in arch['edges'])
                if not has_incoming:
                    arch['edges'].append({
                        'from': f'ROOT_{arch_hash}',
                        'to': comp['id'],
                        'label': 'Contains',
                        'type': 'data'
                    })

        # Validate edges reference existing components
        component_ids = {c['id'] for c in arch['components']}
        arch['edges'] = [
            e for e in arch['edges']
            if e.get('from') in component_ids and e.get('to') in component_ids
        ]

        return arch

    def _calculate_layout(self, arch: Dict) -> Dict:
        """Calculate x,y positions for all components using hierarchical layout."""
        components = arch['components']
        if not components:
            return arch

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

        # Assign level 1 to any orphan nodes (not connected to root)
        for comp in components:
            if comp['id'] not in levels:
                levels[comp['id']] = 1

        # Group by level
        level_groups = {}
        for comp in components:
            level = levels.get(comp['id'], 0)
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(comp)

        # Assign positions
        canvas_center = 500
        for level, comps in level_groups.items():
            y = 50 + (level * 150)
            width = len(comps) * 200
            start_x = canvas_center - (width / 2) + 100

            for i, comp in enumerate(comps):
                comp['x'] = int(start_x + (i * 200))
                comp['y'] = y

        return arch

    def _save_to_database(self, project_id: str, architecture: Dict):
        """Save architecture to database, replacing existing."""
        # Delete existing components, edges, metrics, test_cases
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

    def _fallback_architecture(self, project) -> Dict:
        """Generate minimal architecture when LLM fails."""
        return {
            "components": [
                {
                    "id": "comp_core",
                    "label": "Core System",
                    "type": "node",
                    "summary": "Main system functionality",
                    "problem": "Implements primary project goals",
                    "goals": ["Complete core functionality"],
                    "inputs": ["User Input"],
                    "outputs": ["System Output"],
                    "requirements": ["Must function as specified"],
                    "risks": ["Architecture may need refinement"],
                    "metrics": [
                        {"req": "Functional completeness", "value": "TBD", "status": "pending", "weight": 2.0}
                    ],
                    "testCases": [
                        {"name": "Core functionality test", "status": "pending", "weight": 1.0}
                    ]
                }
            ],
            "edges": [],
            "architecture_notes": "Fallback architecture - manual refinement recommended"
        }

    def to_graph_data(self, architecture: Dict, project_id: str) -> Dict[str, Any]:
        """Convert architecture to Graph.html format."""
        project = self.db.get_project(project_id)
        global_tasks = self.db.get_global_tasks(project_id)
        agents = self.db.get_all_agents()

        return {
            "projectName": project.name if project else "Unknown",
            "projectSummary": project.summary if project else "",
            "phase": "design",
            "globalTasks": [gt.to_graph_task() for gt in global_tasks],
            "agents": [
                a.to_graph_agent() for a in agents
            ],
            "nodes": architecture.get("components", []),
            "edges": architecture.get("edges", []),
            "architectureNotes": architecture.get("architecture_notes", "")
        }
