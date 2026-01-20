"""
Interviewer Agent - Phase 1 of the orchestration pipeline.
Analyzes user input and creates structured project briefs.
"""
import os
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from .base_agent import BaseAgent

# Add parent directory to path for db import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import Database, Project, Component


class InterviewerAgent(BaseAgent):
    """
    Conducts project interviews and generates structured briefs.

    Scope: User conversation only
    Inputs: User's project description
    Outputs: Structured project brief (JSON)
    """

    def __init__(self, db: Database, model: Optional[str] = None):
        """
        Initialize the interviewer agent.

        Args:
            db: Database instance for persistence
            model: Optional model override (e.g., 'claude-haiku-4-5-20251001')
        """
        # Create config with model override if provided
        from .base_agent import AgentConfig
        config = AgentConfig(model=model) if model else None

        super().__init__(
            agent_id=f"interviewer_{uuid.uuid4().hex[:8]}",
            agent_type="interviewer",
            db=db,
            config=config
        )

    def get_scoped_context(self) -> Dict[str, Any]:
        """Interviewer only sees user input - nothing else."""
        return {
            "role": "interviewer",
            "access": ["user_input"],
            "restrictions": ["no_existing_code", "no_other_agents"]
        }

    def execute(self, user_prompt: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a project description and generate a structured brief.

        Args:
            user_prompt: The user's project description
            project_id: Optional existing project ID to update

        Returns:
            Structured project brief with components, edges, requirements
        """
        self.log('start', f'Analyzing project description ({len(user_prompt)} chars)')

        # Call Claude with the interviewer prompt
        system_prompt = self.get_system_prompt()

        try:
            response = self.call_claude(
                prompt=f"Analyze this project description and create a structured brief:\n\n{user_prompt}",
                system=system_prompt,
                expect_json=True
            )

            # Parse the response
            brief = self.parse_json_response(response)

        except Exception as e:
            self.log('error', f'Failed to get Claude response: {e}')
            # Return fallback structure on failure
            brief = self._fallback_brief(user_prompt)

        # Validate and enhance the brief
        brief = self._validate_brief(brief, user_prompt)

        # Build transcript from initial conversation
        transcript = f"[{datetime.now().isoformat()}] USER:\n{user_prompt}\n\n"
        transcript += f"[{datetime.now().isoformat()}] INTERVIEWER:\nAnalyzed project and identified {len(brief.get('components', []))} components.\n"
        if brief.get('questions'):
            transcript += f"Clarifying questions:\n" + "\n".join(f"- {q}" for q in brief['questions'])
        brief['_transcript'] = transcript

        # Save to database
        project = self._save_to_database(brief, project_id)
        brief['project_id'] = project.id

        self.log('complete', f'Generated brief with {len(brief.get("components", []))} components')

        return brief

    def _validate_brief(self, brief: Dict[str, Any], original_prompt: str) -> Dict[str, Any]:
        """Ensure brief has all required fields with defaults."""
        defaults = {
            "title": "Untitled Project",
            "summary": original_prompt[:200],
            "problem": "Not specified",
            "goals": [],
            "components": [],
            "edges": [],
            "global_requirements": [],
            "global_risks": [],
            "questions": [],
            "mermaid_diagram": ""
        }

        for key, default in defaults.items():
            if key not in brief or brief[key] is None:
                brief[key] = default

        # Generate truly unique prefix using UUID (not hash-based, to avoid collisions)
        import time
        unique_prefix = f"{uuid.uuid4().hex[:8]}_{int(time.time() * 1000) % 100000}"

        # Build mapping from old IDs to new IDs for edge updates
        id_mapping = {}

        # Ensure components have required Graph.html fields
        for i, comp in enumerate(brief.get("components", [])):
            old_id = comp.get("id", f"comp_{i}")
            new_id = f"c_{unique_prefix}_{i}"
            id_mapping[old_id] = new_id
            comp["id"] = new_id
            comp.setdefault("label", f"Component {i+1}")
            comp.setdefault("type", "node")
            comp.setdefault("status", "pending")
            comp.setdefault("x", 500)
            comp.setdefault("y", 100 + (i * 150))
            comp.setdefault("summary", "")
            comp.setdefault("problem", "")
            comp.setdefault("goals", [])
            comp.setdefault("scope", [])
            comp.setdefault("requirements", [])
            comp.setdefault("risks", [])
            comp.setdefault("inputs", [])
            comp.setdefault("outputs", [])
            comp.setdefault("files", [])
            comp.setdefault("subtasks", [])
            comp.setdefault("metrics", [])
            # Normalize testCases - ensure they have proper structure
            test_cases = comp.get("testCases", [])
            normalized_tests = []
            for tc in test_cases:
                if isinstance(tc, str):
                    normalized_tests.append({"name": tc, "type": "unit", "priority": "medium"})
                elif isinstance(tc, dict):
                    normalized_tests.append({
                        "name": tc.get("name", "Unnamed test"),
                        "type": tc.get("type", "unit"),
                        "priority": tc.get("priority", "medium")
                    })
            comp["testCases"] = normalized_tests if normalized_tests else []

        # Update edge references to use new component IDs
        for edge in brief.get("edges", []):
            if edge.get("from") in id_mapping:
                edge["from"] = id_mapping[edge["from"]]
            if edge.get("to") in id_mapping:
                edge["to"] = id_mapping[edge["to"]]

        # Add root node if not present
        has_root = any(c.get("type") == "root" for c in brief["components"])
        if not has_root and brief["components"]:
            root_id = f"ROOT_{unique_prefix}"
            root_node = {
                "id": root_id,
                "label": brief["title"],
                "type": "root",
                "status": "active",
                "x": 500,
                "y": 50,
                "summary": brief["summary"],
                "problem": brief["problem"],
                "goals": brief["goals"],
                "scope": [],
                "requirements": brief["global_requirements"],
                "risks": brief["global_risks"],
                "inputs": ["User Request"],
                "outputs": ["Completed System"],
                "files": [],
                "subtasks": [],
                "metrics": [],
                "testCases": []
            }
            brief["components"].insert(0, root_node)

            # Add edge from root to first component
            if len(brief["components"]) > 1:
                brief["edges"].insert(0, {
                    "from": root_id,
                    "to": brief["components"][1]["id"],
                    "label": "Initiates",
                    "type": "data"
                })

        # CRITICAL: Ensure questions are never empty on initial analysis
        # This guarantees the clarify phase is always shown
        if not brief.get("questions") and brief.get("refinement_iteration", 0) == 0:
            brief["questions"] = [
                "What is the expected scale of this project (number of users, data volume)?",
                "Are there any specific technologies or frameworks you prefer or need to integrate with?",
                "What are the most critical features that must work perfectly?",
                "Are there any security, compliance, or regulatory requirements to consider?"
            ]

        return brief

    def _fallback_brief(self, user_prompt: str) -> Dict[str, Any]:
        """Generate minimal brief when LLM parsing fails."""
        return {
            "title": "New Project",
            "summary": user_prompt[:500],
            "problem": "Extracted from user description",
            "goals": ["Complete the project as described"],
            "components": [
                {
                    "id": "comp_main",
                    "label": "Main Component",
                    "type": "node",
                    "summary": "Primary implementation",
                    "inputs": ["User Input"],
                    "outputs": ["Project Output"],
                    "requirements": [],
                    "risks": []
                }
            ],
            "edges": [],
            "global_requirements": [],
            "global_risks": ["Requirements may need clarification"],
            "questions": ["Could you provide more details about the project?"]
        }

    def _save_to_database(self, brief: Dict[str, Any], project_id: Optional[str] = None) -> Project:
        """Save the brief to the database."""
        transcript = brief.get('_transcript', '')

        # Create or update project
        if project_id:
            project = self.db.get_project(project_id)
            if project:
                # Append to existing transcript
                existing_transcript = project.transcript or ''
                if transcript:
                    transcript = existing_transcript + "\n\n" + transcript if existing_transcript else transcript
                self.db.update_project(project_id, {
                    'name': brief['title'],
                    'summary': brief['summary'],
                    'problem': brief['problem'],
                    'questions': brief.get('questions', []),
                    'transcript': transcript,
                    'phase': 'interview'
                })
            else:
                project_id = None

        if not project_id:
            project_id = f"proj_{uuid.uuid4().hex[:8]}"
            self.db.create_project(
                id=project_id,
                name=brief['title'],
                summary=brief['summary'],
                problem=brief['problem'],
                questions=brief.get('questions', []),
                phase='interview'
            )
            # Save transcript separately since create_project doesn't have transcript param
            if transcript:
                self.db.update_project(project_id, {'transcript': transcript})

        # Save components
        for comp in brief.get('components', []):
            self.db.create_component(
                id=comp['id'],
                project_id=project_id,
                label=comp['label'],
                type=comp.get('type', 'node'),
                status=comp.get('status', 'pending'),
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

        # Save edges (only if both components exist)
        component_ids = {c['id'] for c in brief.get('components', [])}
        for edge in brief.get('edges', []):
            from_id = edge.get('from', '')
            to_id = edge.get('to', '')
            # Only create edge if both components exist
            if from_id in component_ids and to_id in component_ids:
                self.db.create_edge(
                    project_id=project_id,
                    from_id=from_id,
                    to_id=to_id,
                    label=edge.get('label', ''),
                    type=edge.get('type', 'data')
                )

        # Save global tasks (phases)
        global_phases = [
            ("Phase 1: Interview - Gather requirements", True),
            ("Phase 2: Design - Create component tree", False),
            ("Phase 3: Visualize - User reviews design", False),
            ("Phase 4: Plan - General Manager creates work plan", False),
            ("Phase 5: Breakdown - Managers create tasks", False),
            ("Phase 6: Assign - Managers assign agents", False),
            ("Phase 7: Execute - Agents complete tasks", False)
        ]
        for i, (text, done) in enumerate(global_phases):
            self.db.create_global_task(
                project_id=project_id,
                text=text,
                done=done,
                sort_order=i
            )

        # Create interviewer agent record
        self.db.create_agent(
            id=self.agent_id,
            name="Interviewer",
            dept="DISC",
            initials="IN",
            status="complete"
        )

        return self.db.get_project(project_id)

    def refine(
        self,
        original_brief: Dict[str, Any],
        answers: Dict[str, str],
        additional_context: str = ""
    ) -> Dict[str, Any]:
        """
        Refine an existing brief based on user answers to clarifying questions.

        Args:
            original_brief: The previous brief with questions
            answers: Dict mapping question text to user's answer
            additional_context: Any additional information from the user

        Returns:
            Refined project brief with updated components
        """
        self.log('refine_start', f'Refining brief with {len(answers)} answers')

        # Build transcript entry for this refinement
        transcript = f"\n[{datetime.now().isoformat()}] REFINEMENT #{original_brief.get('refinement_iteration', 0) + 1}:\n"
        for q, a in answers.items():
            transcript += f"Q: {q}\nA: {a}\n\n"
        if additional_context:
            transcript += f"Additional context: {additional_context}\n"

        # Build the refinement prompt
        original_summary = original_brief.get('summary', '')
        original_questions = original_brief.get('questions', [])

        qa_section = "\n".join([
            f"Q: {q}\nA: {answers.get(q, 'Not answered')}"
            for q in original_questions
            if q in answers
        ])

        refinement_prompt = f"""I previously analyzed this project and had some clarifying questions.

ORIGINAL PROJECT DESCRIPTION:
{original_summary}

ORIGINAL COMPONENTS IDENTIFIED:
{', '.join([c['label'] for c in original_brief.get('components', [])])}

QUESTIONS AND ANSWERS:
{qa_section}

{f"ADDITIONAL CONTEXT FROM USER: {additional_context}" if additional_context else ""}

Based on the answers provided, please generate an UPDATED and MORE DETAILED project brief.
- Refine the components based on the clarified requirements
- Add new components if the answers reveal additional needs
- Update requirements and risks based on new information
- Generate new clarifying questions ONLY if critical information is still missing
- If the project is now well-defined, return an empty questions array

Analyze this and create an updated structured brief:"""

        system_prompt = self.get_system_prompt()

        try:
            response = self.call_claude(
                prompt=refinement_prompt,
                system=system_prompt,
                expect_json=True
            )
            refined_brief = self.parse_json_response(response)
        except Exception as e:
            self.log('error', f'Failed to refine brief: {e}')
            # Return original with a note
            refined_brief = original_brief.copy()
            refined_brief['refinement_error'] = str(e)

        # Validate the refined brief
        refined_brief = self._validate_brief(refined_brief, original_summary)

        # Track refinement iteration
        refined_brief['refinement_iteration'] = original_brief.get('refinement_iteration', 0) + 1
        refined_brief['project_id'] = original_brief.get('project_id')

        # Add transcript entry for this refinement
        transcript += f"[{datetime.now().isoformat()}] INTERVIEWER:\nRefined to {len(refined_brief.get('components', []))} components.\n"
        if refined_brief.get('questions'):
            transcript += f"New clarifying questions:\n" + "\n".join(f"- {q}" for q in refined_brief['questions'])

        # Save transcript to database
        project_id = original_brief.get('project_id')
        if project_id and self.db:
            project = self.db.get_project(project_id)
            if project:
                existing_transcript = project.transcript or ''
                full_transcript = existing_transcript + transcript
                self.db.update_project(project_id, {'transcript': full_transcript})

        self.log('refine_complete', f'Refined to {len(refined_brief.get("components", []))} components')

        return refined_brief

    def is_ready_for_design(self, brief: Dict[str, Any]) -> bool:
        """
        Check if the brief is complete enough to proceed to design phase.

        Returns True if:
        - At least one refinement iteration has occurred
        - No critical questions remain
        - At least 2 components identified
        - Has clear goals
        """
        questions = brief.get('questions', [])
        components = brief.get('components', [])
        goals = brief.get('goals', [])
        refinement_iteration = brief.get('refinement_iteration', 0)

        # Filter out root node for component count
        real_components = [c for c in components if c.get('type') != 'root']

        # Must have gone through at least one refinement (answered questions)
        # AND have no remaining questions
        return (
            refinement_iteration >= 1 and
            len(questions) == 0 and
            len(real_components) >= 2 and
            len(goals) >= 1
        )

    def to_graph_data(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Convert brief to Graph.html format."""
        return {
            "projectName": brief.get("title", "Untitled"),
            "projectSummary": brief.get("summary", ""),
            "questions": brief.get("questions", []),
            "readyForDesign": self.is_ready_for_design(brief),
            "refinementIteration": brief.get("refinement_iteration", 0),
            "globalTasks": [
                {"text": "Phase 1: Interview - Gather requirements", "done": True},
                {"text": "Phase 2: Design - Create component tree", "done": False},
                {"text": "Phase 3: Visualize - User reviews design", "done": False},
                {"text": "Phase 4: Plan - General Manager creates work plan", "done": False},
                {"text": "Phase 5: Breakdown - Managers create tasks", "done": False},
                {"text": "Phase 6: Assign - Managers assign agents", "done": False},
                {"text": "Phase 7: Execute - Agents complete tasks", "done": False}
            ],
            "agents": [
                {"id": self.agent_id, "name": "Interviewer", "dept": "DISC", "initials": "IN", "status": "complete"}
            ],
            "nodes": brief.get("components", []),
            "edges": brief.get("edges", []),
            "mermaidDiagram": brief.get("mermaid_diagram", ""),
            "timestamp": datetime.now().isoformat()
        }
