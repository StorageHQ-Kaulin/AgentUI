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

        # Clear existing design for this project before saving new one
        self.db.delete_components(project_id)
        self.db.delete_edges(project_id)

        components = design.get('components', [])
        edges = design.get('edges', [])

        self.log('info', f"Persisting {len(components)} components and {len(edges)} edges")

        for comp in components:
            # Ensure required fields
            comp_id = comp.get('id') or f"comp_{uuid.uuid4().hex[:8]}"

            # Handle both 'problem' and 'problem_statement' from architect output
            problem = comp.get('problem') or comp.get('problem_statement')

            # Create component with all fields
            # Note: database.py handles JSON serialization internally
            self.db.create_component(
                id=comp_id,
                project_id=project_id,
                label=comp.get('label', 'Unknown Component'),
                type=comp.get('type', 'node'),
                parent_id=comp.get('parent_id'),
                summary=comp.get('summary'),
                problem=problem,
                goals=comp.get('goals', []),
                scope=comp.get('scope', []),
                requirements=comp.get('requirements', []),
                risks=comp.get('risks', []),
                inputs=comp.get('inputs', []),
                outputs=comp.get('outputs', []),
                files=comp.get('files', [])
            )

            # Save metrics to metrics table
            for metric in comp.get('metrics', []):
                self.db.create_metric(
                    component_id=comp_id,
                    requirement=metric.get('name', 'Unknown Metric'),
                    value=metric.get('target'),
                    status=metric.get('status', 'pending'),
                    weight=metric.get('weight', 1.0)
                )

            # Save test cases to test_cases table
            for test in comp.get('test_cases', []):
                self.db.create_test_case(
                    component_id=comp_id,
                    name=test.get('name', 'Unknown Test'),
                    status=test.get('status', 'pending'),
                    value=test.get('description'),
                    weight=test.get('weight', 1.0)
                )

        for edge in edges:
            # Handle both 'from'/'to' and 'from_id'/'to_id' formats
            from_id = edge.get('from_id') or edge.get('from')
            to_id = edge.get('to_id') or edge.get('to')

            if from_id and to_id:
                self.db.create_edge(
                    project_id=project_id,
                    from_id=from_id,
                    to_id=to_id,
                    label=edge.get('label'),
                    type=edge.get('type', 'data')
                )

        # Save architecture notes to project if present
        arch_notes = design.get('architecture_notes')
        if arch_notes:
            # Append architecture notes to project work_plan field
            self.db.update_project(project_id, {'work_plan': arch_notes})
