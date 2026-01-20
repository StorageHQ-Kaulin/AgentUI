"""
API routes for the orchestrator dashboard.
Handles all REST API endpoints.
"""
import os
import sys
from typing import Optional, Dict, Any

# Add parent directory to path for db import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import Database
from .serializers import GraphSerializer


class APIHandler:
    """Handles API route logic."""

    def __init__(self, db: Database):
        """
        Initialize the API handler.

        Args:
            db: Database instance
        """
        self.db = db
        self.serializer = GraphSerializer(db)

    # =========================================================================
    # PROJECT ENDPOINTS
    # =========================================================================

    def get_projects(self) -> Dict[str, Any]:
        """
        List all projects.

        GET /api/projects

        Returns:
            {"projects": [...]}
        """
        return self.serializer.serialize_project_list()

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get project details.

        GET /api/projects/:id

        Returns:
            Project details or None if not found
        """
        project = self.db.get_project(project_id)
        if not project:
            return None
        return project.to_dict()

    def get_project_graph(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get project in Graph.html format.

        GET /api/projects/:id/graph

        Returns:
            Graph.html formatted data or None if not found
        """
        return self.serializer.serialize_project(project_id)

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a project.

        PATCH /api/projects/:id

        Args:
            project_id: Project ID
            updates: Fields to update

        Returns:
            {"status": "success", "updated": [...]} or error
        """
        project = self.db.get_project(project_id)
        if not project:
            return {"status": "error", "message": "Project not found"}

        # Filter allowed updates
        allowed_fields = {'name', 'phase', 'summary', 'problem'}
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}

        if filtered:
            self.db.update_project(project_id, filtered)

        return {"status": "success", "updated": list(filtered.keys())}

    def delete_project(self, project_id: str) -> Dict[str, Any]:
        """
        Delete a project.

        DELETE /api/projects/:id

        Returns:
            {"status": "success"} or error
        """
        if self.db.delete_project(project_id):
            return {"status": "success"}
        return {"status": "error", "message": "Project not found"}

    def approve_design(self, project_id: str) -> Dict[str, Any]:
        """
        Approve design and advance to next phase.

        POST /api/projects/:id/approve

        Returns:
            {"status": "success", "new_phase": "..."} or error
        """
        project = self.db.get_project(project_id)
        if not project:
            return {"status": "error", "message": "Project not found"}

        # Phase progression order
        phase_order = ['interview', 'design', 'visualize', 'planning', 'breakdown', 'assign', 'execute']

        try:
            current_idx = phase_order.index(project.phase)
        except ValueError:
            current_idx = 0

        next_phase = phase_order[min(current_idx + 1, len(phase_order) - 1)]

        # Update phase
        self.db.update_project(project_id, {'phase': next_phase})

        # Mark current global task as done
        self.db.mark_global_task_done(project_id, f"Phase {current_idx + 1}")

        return {"status": "success", "new_phase": next_phase, "previous_phase": project.phase}

    # =========================================================================
    # COMPONENT ENDPOINTS
    # =========================================================================

    def get_component(self, component_id: str) -> Optional[Dict[str, Any]]:
        """
        Get component details.

        GET /api/components/:id

        Returns:
            Component details or None if not found
        """
        return self.serializer.serialize_component_detail(component_id)

    def update_component(self, component_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a component.

        PATCH /api/components/:id

        Args:
            component_id: Component ID
            updates: Fields to update

        Returns:
            {"status": "success", "updated": [...]} or error
        """
        comp = self.db.get_component(component_id)
        if not comp:
            return {"status": "error", "message": "Component not found"}

        # Filter allowed updates
        allowed_fields = {
            'x', 'y', 'status', 'summary', 'problem',
            'goals', 'scope', 'requirements', 'risks',
            'inputs', 'outputs', 'label'
        }
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}

        if filtered:
            self.db.update_component(component_id, filtered)

        return {"status": "success", "updated": list(filtered.keys())}

    def attach_file(self, component_id: str, file_path: str, file_type: str = "file") -> Dict[str, Any]:
        """
        Attach a file to a component.

        POST /api/components/:id/files

        Args:
            component_id: Component ID
            file_path: Path to the file
            file_type: Type of file ("file" or "folder")

        Returns:
            {"status": "success", "files": [...]} or error
        """
        comp = self.db.get_component(component_id)
        if not comp:
            return {"status": "error", "message": "Component not found"}

        files = comp.files or []
        file_name = file_path.split('/')[-1]

        # Check if file already attached
        if any(f.get('path') == file_path for f in files):
            return {"status": "error", "message": "File already attached"}

        files.append({"name": file_name, "path": file_path, "type": file_type})

        self.db.update_component(component_id, {"files": files})
        return {"status": "success", "files": files}

    def remove_file(self, component_id: str, file_path: str) -> Dict[str, Any]:
        """
        Remove a file from a component.

        DELETE /api/components/:id/files

        Args:
            component_id: Component ID
            file_path: Path to the file to remove

        Returns:
            {"status": "success", "files": [...]} or error
        """
        comp = self.db.get_component(component_id)
        if not comp:
            return {"status": "error", "message": "Component not found"}

        files = [f for f in (comp.files or []) if f.get('path') != file_path]

        self.db.update_component(component_id, {"files": files})
        return {"status": "success", "files": files}

    # =========================================================================
    # AGENT ENDPOINTS
    # =========================================================================

    def get_agents(self) -> Dict[str, Any]:
        """
        List all agents.

        GET /api/agents

        Returns:
            {"agents": [...]}
        """
        agents = self.db.get_all_agents()
        return {
            "agents": [a.to_graph_agent() for a in agents]
        }

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent details.

        GET /api/agents/:id

        Returns:
            Agent details or None if not found
        """
        agent = self.db.get_agent(agent_id)
        if not agent:
            return None
        return agent.to_dict()

    # =========================================================================
    # ANALYSIS ENDPOINTS
    # =========================================================================

    def analyze_codebase(self, path: str) -> Dict[str, Any]:
        """
        Analyze a codebase.

        POST /api/analyze

        Args:
            path: Path to the codebase

        Returns:
            Analysis result or error
        """
        try:
            from analyzers import CodebaseScanner
            scanner = CodebaseScanner(path)
            result = scanner.scan()
            return {"status": "success", "analysis": result.to_dict()}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Analysis failed: {str(e)}"}

    # =========================================================================
    # ARCHITECTURE ENDPOINTS
    # =========================================================================

    def generate_architecture(self, project_id: str, codebase_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate architecture for a project.

        POST /api/projects/:id/architecture

        Args:
            project_id: Project ID
            codebase_path: Optional path to existing codebase for analysis

        Returns:
            {"status": "success", "architecture": {...}} or error
        """
        project = self.db.get_project(project_id)
        if not project:
            return {"status": "error", "message": "Project not found"}

        try:
            from agents import ArchitectAgent

            # Optionally analyze codebase first
            codebase_analysis = None
            if codebase_path:
                from analyzers import CodebaseScanner
                try:
                    scanner = CodebaseScanner(codebase_path)
                    analysis = scanner.scan()
                    codebase_analysis = analysis.to_dict()
                except Exception as e:
                    # Continue without codebase analysis
                    pass

            # Run architect
            architect = ArchitectAgent(self.db)
            architecture = architect.execute(project_id, codebase_analysis)

            return {
                "status": "success",
                "architecture": architecture,
                "component_count": len(architecture.get("components", [])),
                "edge_count": len(architecture.get("edges", []))
            }

        except Exception as e:
            return {"status": "error", "message": f"Architecture generation failed: {str(e)}"}
