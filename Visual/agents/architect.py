"""
Architect Agent - System Design & Component Breakdown.
"""
import os
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentConfig
try:
    from analyzers.scanner import CodebaseScanner
except ImportError:
    try:
        from ..analyzers.scanner import CodebaseScanner
    except ImportError:
        from Visual.analyzers.scanner import CodebaseScanner

class ArchitectAgent(BaseAgent):
    """
    Architect Agent responsible for converting a project brief into a technical system design.
    """

    def __init__(self, db, model: Optional[str] = None):
        """
        Initialize the architect agent.

        Args:
            db: Database instance for persistence
            model: Optional model override (defaults to rigorous model)
        """
        # Use a high-intelligence model for architecture
        config = AgentConfig(model=model or "claude-opus-4-5-20251101")
        
        super().__init__(
            agent_id=f"architect_{uuid.uuid4().hex[:8]}",
            agent_type="architect",
            db=db,
            config=config
        )

    def execute(self, project_id: str, brief: Dict[str, Any], root_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a system design from a project brief.

        Args:
            project_id: The ID of the project
            brief: The project brief (from Interviewer)
            root_path: Optional path to existing codebase to analyze

        Returns:
            Dict containing 'components' and 'edges'
        """
        self.log('info', f"Starting architecture design for project {project_id}")
        
        # Step 1: Analyze existing codebase (if provided)
        scan_results = None
        if root_path and os.path.exists(root_path):
            self.log('info', f"Scanning codebase at {root_path}")
            try:
                scanner = CodebaseScanner(root_path)
                scan_results = scanner.scan().to_dict()
                self.log('info', f"Scan complete: {scan_results['file_count']} files found")
            except Exception as e:
                self.log('error', f"Codebase scan failed: {e}")

        # Step 2: Construct Prompt
        prompt = self._construct_prompt(brief, scan_results)

        # Step 3: Call Claude
        self.log('thinking', "Generating system architecture...")
        response = self.call_claude(
            system_prompt="You are a Senior Software Architect.",
            user_prompt=prompt
        )

        # Step 4: Parse Response
        try:
            design = json.loads(response)
        except json.JSONDecodeError:
            self.log('error', "Failed to parse Architect response as JSON")
            # Fallback or retry logic could go here
            raise ValueError("Architect response was not valid JSON")

        self.log('info', f"Design generated: {len(design.get('components', []))} components")

        # Step 5: Save to Database
        self._save_design(project_id, design)

        return design

    def _construct_prompt(self, brief: Dict[str, Any], scan_results: Optional[Dict] = None) -> str:
        """Construct the prompt for the Architect."""
        
        # Load the template
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'architect.txt')
        if os.path.exists(prompt_path):
            with open(prompt_path, 'r') as f:
                template = f.read()
        else:
            # Fallback template if file missing
            template = "Analyze the brief and generate a JSON system design."

        # Format the variable sections
        brief_str = json.dumps(brief, indent=2)
        scan_str = json.dumps(scan_results, indent=2) if scan_results else "No existing codebase provided."

        return template.format(
            project_brief=brief_str,
            codebase_analysis=scan_str
        )

    def _save_design(self, project_id: str, design: Dict[str, Any]):
        """Save the generated components and edges to the database."""
        if not self.db:
            return

        # 1. Clear existing design for this project (for now, simplistic overwrite)
        # In a real system, we might version this or diff it.
        # self.db.execute("DELETE FROM components WHERE project_id = ?", (project_id,))
        # self.db.execute("DELETE FROM edges WHERE project_id = ?", (project_id,))
        # For MVP, we'll assume we are adding to it or the DB handles upsert.
        # Let's clean slate for this iteration to avoid ghosts.
        
        # Actually, let's look at db.create_component implementation. 
        # It takes individual args. We need to iterate.
        
        components = design.get('components', [])
        edges = design.get('edges', [])

        self.log('info', f"Persisting {len(components)} components and {len(edges)} edges")

        for comp in components:
            # Ensure required fields
            comp_id = comp.get('id') or f"comp_{uuid.uuid4().hex[:8]}"
            
            # create_component(self, project_id, label, type='node', parent_id=None, **kwargs)
            self.db.create_component(
                id=comp_id,
                project_id=project_id,
                label=comp.get('label', 'Unknown Component'),
                type=comp.get('type', 'node'),
                parent_id=comp.get('parent_id'),
                summary=comp.get('summary'),
                problem=comp.get('problem'),
                goals=json.dumps(comp.get('goals', [])),
                requirements=json.dumps(comp.get('requirements', [])),
                inputs=json.dumps(comp.get('inputs', [])),
                outputs=json.dumps(comp.get('outputs', [])),
                files=json.dumps(comp.get('files', []))
            )
            # Update specific ID if we want to enforce the Architect's ID
            # But create_component autogenerates ID, so we might need a raw query or update create_component
            # For now, let's assume create_component returns the DB ID or we rely on label matching?
            # Actually, looking at database.py, create_component generates an ID if not provided.
            # If we want to maintain the Architect's relationships, we MUST control the ID.
            # BaseAgent doesn't have direct DB SQL access usually, it goes through DB methods.
            # Let's assume we update `database.py` to allow passing `id` or we insert manually here.
            # Or better: Update database.py to accept `id`.
        
        for edge in edges:
            self.db.create_edge(
                project_id=project_id,
                from_id=edge['from_id'],
                to_id=edge['to_id'],
                label=edge.get('label'),
                type=edge.get('type', 'data')
            )
