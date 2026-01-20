"""
Serializers to convert database models to Graph.html format.
"""
import os
import sys
from typing import Dict, Any, List, Optional

# Add parent directory to path for db import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import Database


class GraphSerializer:
    """Converts database data to Graph.html format."""

    def __init__(self, db: Database):
        """
        Initialize the serializer.

        Args:
            db: Database instance
        """
        self.db = db

    def serialize_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Serialize a project to full Graph.html format.

        Matches the structure expected by Graph.html:
        - projectName
        - projectSummary
        - phase
        - globalTasks
        - agents
        - nodes (components)
        - edges

        Args:
            project_id: The project ID to serialize

        Returns:
            Dictionary in Graph.html format, or None if project not found
        """
        project = self.db.get_project(project_id)
        if not project:
            return None

        components = self.db.get_components(project_id)
        edges = self.db.get_edges(project_id)
        global_tasks = self.db.get_global_tasks(project_id)
        agents = self.db.get_agents_for_project(project_id)

        return {
            "projectId": project.id,
            "projectName": project.name,
            "projectSummary": project.summary or "",
            "projectProblem": project.problem or "",
            "phase": project.phase,
            "globalTasks": [
                {"text": gt.text, "done": bool(gt.done)}
                for gt in global_tasks
            ],
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "dept": a.dept or "DEV",
                    "initials": a.initials or a.name[:2].upper(),
                    "status": a.status
                }
                for a in agents
            ],
            "nodes": [
                self._serialize_component(c)
                for c in components
            ],
            "edges": [
                {
                    "from": e.from_id,
                    "to": e.to_id,
                    "label": e.label or "",
                    "type": e.type or "data"
                }
                for e in edges
            ],
            "timestamp": project.updated_at
        }

    def _serialize_component(self, comp) -> Dict[str, Any]:
        """
        Serialize a single component to Graph.html node format.

        Args:
            comp: Component model instance

        Returns:
            Dictionary in Graph.html node format
        """
        # Get metrics and test cases
        metrics = self.db.get_metrics(comp.id)
        test_cases = self.db.get_test_cases(comp.id)

        return {
            "id": comp.id,
            "label": comp.label,
            "x": comp.x or 500,
            "y": comp.y or 100,
            "type": comp.type or "node",
            "agentId": comp.agent_id,
            "status": comp.status or "pending",
            "lastEdited": comp.last_edited,
            "summary": comp.summary or "",
            "problem": comp.problem or "",
            "goals": comp.goals or [],
            "scope": comp.scope or [],
            "requirements": comp.requirements or [],
            "risks": comp.risks or [],
            "inputs": comp.inputs or [],
            "outputs": comp.outputs or [],
            "files": comp.files or [],
            "subtasks": comp.subtasks or [],
            "metrics": [
                {
                    "req": m.requirement,
                    "value": m.value or "TBD",
                    "status": m.status,
                    "weight": m.weight
                }
                for m in metrics
            ],
            "testCases": [
                {
                    "name": tc.name,
                    "status": tc.status,
                    "value": tc.value,
                    "weight": tc.weight
                }
                for tc in test_cases
            ]
        }

    def serialize_project_list(self) -> Dict[str, Any]:
        """
        Serialize all projects to a list format.

        Returns:
            Dictionary with projects array
        """
        projects = self.db.get_all_projects()
        return {
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "phase": p.phase,
                    "summary": p.summary or "",
                    "created_at": p.created_at,
                    "updated_at": p.updated_at
                }
                for p in projects
            ]
        }

    def serialize_component_detail(self, component_id: str) -> Optional[Dict[str, Any]]:
        """
        Serialize a single component with full details.

        Args:
            component_id: The component ID

        Returns:
            Component dictionary or None if not found
        """
        comp = self.db.get_component(component_id)
        if not comp:
            return None
        return self._serialize_component(comp)
