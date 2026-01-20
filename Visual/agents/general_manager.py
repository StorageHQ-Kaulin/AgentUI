"""
General Manager Agent - Phase 4 of the orchestration pipeline.
Analyzes components and creates detailed file-by-file build plans.
"""
import os
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentConfig


class GeneralManagerAgent(BaseAgent):
    """
    General Manager Agent responsible for:
    1. Analyzing each component individually
    2. Creating file-by-file build plans
    3. Validating plans match component requirements
    4. Spawning managers for each component
    """

    def __init__(self, db, model: Optional[str] = None):
        """
        Initialize the general manager agent.

        Args:
            db: Database instance for persistence
            model: Optional model override
        """
        config = AgentConfig(model=model or "claude-sonnet-4-20250514")

        super().__init__(
            agent_id=f"gm_{uuid.uuid4().hex[:8]}",
            agent_type="general_manager",
            db=db,
            config=config
        )

    def get_scoped_context(self) -> Dict[str, Any]:
        """GM sees all components but not implementation details."""
        return {
            "role": "general_manager",
            "access": ["components", "edges", "project_summary"],
            "restrictions": ["no_code_access", "no_task_details"]
        }

    def execute(self, project_id: str) -> Dict[str, Any]:
        """
        Execute GM phase: analyze components and create build plans.

        Args:
            project_id: The project to process

        Returns:
            Dict containing work_plan and component_plans
        """
        self.log('info', f"Starting GM phase for project {project_id}")

        # Get project and components
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        components = self.db.get_components_by_project(project_id)
        edges = self.db.get_edges_by_project(project_id)

        # Filter out root node for planning
        plannable_components = [c for c in components if c.type != 'root']

        self.log('info', f"Found {len(plannable_components)} components to plan")

        # Phase 1: Create build plan for each component
        component_plans = []
        for comp in plannable_components:
            self.log('thinking', f"Analyzing component: {comp.label}")
            plan = self._create_component_plan(comp, edges, components)
            component_plans.append(plan)

            # Save plan to component subtasks
            self._save_component_plan(comp.id, plan)

        # Phase 2: Review and validate all plans
        self.log('thinking', "Reviewing all component plans...")
        validated_plans = self._validate_plans(project, component_plans, edges)

        # Phase 3: Determine execution order
        execution_order = self._determine_execution_order(validated_plans, edges)

        # Phase 4: Create managers for each component
        self._create_managers(project_id, plannable_components)

        # Phase 5: Save overall work plan
        work_plan = {
            'created_at': datetime.now().isoformat(),
            'created_by': self.agent_id,
            'total_components': len(plannable_components),
            'execution_order': execution_order,
            'component_plans': validated_plans
        }

        self.db.update_project(project_id, {
            'work_plan': json.dumps(work_plan),
            'phase': 'planning'
        })

        self.log('info', f"GM phase complete. Created plans for {len(component_plans)} components")

        return work_plan

    def _create_component_plan(
        self,
        component,
        edges: List,
        all_components: List
    ) -> Dict[str, Any]:
        """
        Create a detailed file-by-file build plan for a single component.
        """
        # Find dependencies
        upstream = []
        downstream = []
        for edge in edges:
            if edge.to_id == component.id:
                dep = next((c for c in all_components if c.id == edge.from_id), None)
                if dep:
                    upstream.append({'id': dep.id, 'label': dep.label, 'type': dep.type})
            if edge.from_id == component.id:
                dep = next((c for c in all_components if c.id == edge.to_id), None)
                if dep:
                    downstream.append({'id': dep.id, 'label': dep.label, 'type': dep.type})

        # Load prompt template
        prompt = self._build_component_prompt(component, upstream, downstream)

        # Call Claude for analysis
        response = self.call_claude(
            system_prompt="You are a Senior Technical Lead creating detailed build plans.",
            user_prompt=prompt
        )

        # Parse response
        try:
            plan = json.loads(response)
        except json.JSONDecodeError:
            self.log('warning', f"Failed to parse plan for {component.label}, using fallback")
            plan = self._fallback_plan(component)

        # Add component reference
        plan['component_id'] = component.id
        plan['component_label'] = component.label
        plan['component_type'] = component.type

        return plan

    def _build_component_prompt(
        self,
        component,
        upstream: List[Dict],
        downstream: List[Dict]
    ) -> str:
        """Build the prompt for component analysis."""

        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'gm_component_breakdown.txt')

        if os.path.exists(prompt_path):
            with open(prompt_path, 'r') as f:
                template = f.read()
        else:
            template = self._default_component_template()

        # Format component data
        component_data = {
            'id': component.id,
            'label': component.label,
            'type': component.type,
            'summary': component.summary or '',
            'problem': component.problem or '',
            'goals': component.goals or [],
            'scope': component.scope or [],
            'requirements': component.requirements or [],
            'risks': component.risks or [],
            'inputs': component.inputs or [],
            'outputs': component.outputs or [],
            'files': component.files or []
        }

        return template.format(
            component_json=json.dumps(component_data, indent=2),
            upstream_deps=json.dumps(upstream, indent=2),
            downstream_deps=json.dumps(downstream, indent=2)
        )

    def _default_component_template(self) -> str:
        """Fallback template if file not found."""
        return """Analyze this component and create a detailed build plan.

COMPONENT:
{component_json}

UPSTREAM DEPENDENCIES (this component receives from):
{upstream_deps}

DOWNSTREAM DEPENDENCIES (this component sends to):
{downstream_deps}

Create a JSON build plan with:
1. files: Array of files to create with path, purpose, and dependencies
2. steps: Ordered implementation steps
3. interfaces: Input/output contracts
4. tests: Test files needed

Return ONLY valid JSON."""

    def _validate_plans(
        self,
        project,
        plans: List[Dict],
        edges: List
    ) -> List[Dict]:
        """
        Second pass: Review all plans for consistency and completeness.
        """
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'gm_validate_plans.txt')

        if os.path.exists(prompt_path):
            with open(prompt_path, 'r') as f:
                template = f.read()
        else:
            template = self._default_validation_template()

        prompt = template.format(
            project_name=project.name,
            project_summary=project.summary or '',
            plans_json=json.dumps(plans, indent=2),
            edges_json=json.dumps([{'from': e.from_id, 'to': e.to_id, 'type': e.type} for e in edges], indent=2)
        )

        response = self.call_claude(
            system_prompt="You are a Technical Architect reviewing build plans for consistency.",
            user_prompt=prompt
        )

        try:
            result = json.loads(response)
            validated_plans = result.get('validated_plans', plans)

            # Log any issues found
            issues = result.get('issues', [])
            for issue in issues:
                self.log('warning', f"Plan issue: {issue}")

            return validated_plans
        except json.JSONDecodeError:
            self.log('warning', "Validation parse failed, returning original plans")
            return plans

    def _default_validation_template(self) -> str:
        """Fallback validation template."""
        return """Review these build plans for consistency.

PROJECT: {project_name}
SUMMARY: {project_summary}

COMPONENT BUILD PLANS:
{plans_json}

COMPONENT CONNECTIONS:
{edges_json}

Check for:
1. Missing file dependencies between components
2. Interface mismatches
3. Gaps in the implementation
4. Duplicate functionality

Return JSON with:
- validated_plans: The plans (with any corrections)
- issues: Array of issues found
- suggestions: Array of improvements

Return ONLY valid JSON."""

    def _determine_execution_order(
        self,
        plans: List[Dict],
        edges: List
    ) -> List[Dict]:
        """
        Determine the order components should be built based on dependencies.
        """
        # Build dependency graph
        component_deps = {}
        for plan in plans:
            comp_id = plan.get('component_id')
            component_deps[comp_id] = {
                'label': plan.get('component_label'),
                'depends_on': [],
                'priority': 0
            }

        # Map dependencies from edges
        for edge in edges:
            if edge.to_id in component_deps:
                component_deps[edge.to_id]['depends_on'].append(edge.from_id)

        # Topological sort for execution order
        order = []
        visited = set()

        def visit(comp_id):
            if comp_id in visited or comp_id not in component_deps:
                return
            visited.add(comp_id)
            for dep_id in component_deps[comp_id]['depends_on']:
                visit(dep_id)
            order.append({
                'component_id': comp_id,
                'label': component_deps[comp_id]['label'],
                'phase': len(order) + 1
            })

        for comp_id in component_deps:
            visit(comp_id)

        return order

    def _create_managers(self, project_id: str, components: List) -> None:
        """Create a manager for each component."""
        for comp in components:
            manager_id = f"mgr_{comp.id}_{uuid.uuid4().hex[:4]}"
            self.db.create_manager(
                id=manager_id,
                project_id=project_id,
                component_id=comp.id,
                status='pending',
                created_by=self.agent_id
            )
            self.log('info', f"Created manager {manager_id} for {comp.label}")

    def _save_component_plan(self, component_id: str, plan: Dict) -> None:
        """Save the build plan to the component's subtasks field."""
        # Convert plan to subtask format
        subtasks = []

        # Add file creation tasks
        for file_info in plan.get('files', []):
            subtasks.append({
                'type': 'file',
                'path': file_info.get('path', ''),
                'purpose': file_info.get('purpose', ''),
                'status': 'pending',
                'dependencies': file_info.get('dependencies', [])
            })

        # Add implementation steps
        for i, step in enumerate(plan.get('steps', [])):
            subtasks.append({
                'type': 'step',
                'order': i + 1,
                'description': step.get('description', step) if isinstance(step, dict) else step,
                'status': 'pending'
            })

        # Add test tasks
        for test in plan.get('tests', []):
            subtasks.append({
                'type': 'test',
                'name': test.get('name', test) if isinstance(test, dict) else test,
                'status': 'pending'
            })

        self.db.update_component(component_id, {'subtasks': subtasks})

    def _fallback_plan(self, component) -> Dict:
        """Generate a minimal fallback plan."""
        return {
            'files': [
                {
                    'path': f"src/{component.label.lower().replace(' ', '_')}/index.py",
                    'purpose': f"Main implementation for {component.label}",
                    'dependencies': []
                },
                {
                    'path': f"tests/test_{component.label.lower().replace(' ', '_')}.py",
                    'purpose': f"Tests for {component.label}",
                    'dependencies': []
                }
            ],
            'steps': [
                {'description': 'Set up file structure', 'order': 1},
                {'description': 'Implement core logic', 'order': 2},
                {'description': 'Add error handling', 'order': 3},
                {'description': 'Write tests', 'order': 4}
            ],
            'interfaces': {
                'inputs': component.inputs or [],
                'outputs': component.outputs or []
            },
            'tests': [
                {'name': f"test_{component.label.lower().replace(' ', '_')}_basic", 'type': 'unit'}
            ]
        }
