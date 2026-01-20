# 1.3 Interviewer Agent

## Objective

Create the first working agent that uses Claude to analyze project descriptions and generate structured project briefs. This replaces the current heuristic-based `agent_logic.py` implementation.

## Files to Create

```
Visual/
├── agents/
│   ├── interviewer.py       # Interviewer agent class
│   └── prompts/
│       └── interviewer.txt  # System prompt for interviews
```

## Current State (to replace)

The existing `agent_logic.py` uses keyword matching:

```python
# Current (BAD - heuristics)
if "scraper" in prompt_lower:
    brief["title"] = "Web Scraper Project"
    brief["core_components"].extend([...])
```

## Target State

Use Claude to intelligently analyze any project description:

```python
# Target (GOOD - LLM)
interviewer = InterviewerAgent(db)
brief = interviewer.execute(user_prompt)
# brief is a structured dict with components, requirements, risks, etc.
```

## Implementation

### prompts/interviewer.txt

```
You are an expert technical interviewer and requirements analyst. Your job is to analyze a user's project description and extract a structured project brief.

ANALYSIS FRAMEWORK:
1. CORE UNDERSTANDING
   - What is the user trying to build?
   - What problem does it solve?
   - Who is the end user?

2. COMPONENT IDENTIFICATION
   - What are the main system components?
   - How do they relate to each other?
   - What are the inputs and outputs of each?

3. REQUIREMENTS EXTRACTION
   - What are the functional requirements?
   - What are the non-functional requirements (performance, scale)?
   - What constraints exist?

4. RISK ASSESSMENT
   - What could go wrong?
   - What dependencies exist?
   - What unknowns need clarification?

OUTPUT FORMAT:
Return a JSON object with this exact structure:
{
    "title": "Project Name",
    "summary": "One paragraph description",
    "problem": "What problem this solves",
    "goals": ["Goal 1", "Goal 2"],
    "components": [
        {
            "id": "comp_1",
            "label": "Component Name",
            "type": "node",
            "summary": "What this component does",
            "inputs": ["Input 1"],
            "outputs": ["Output 1"],
            "requirements": ["Requirement 1"],
            "risks": ["Risk 1"]
        }
    ],
    "edges": [
        {"from": "comp_1", "to": "comp_2", "label": "Data Flow", "type": "data"}
    ],
    "global_requirements": ["Requirement that applies to whole project"],
    "global_risks": ["Risk that applies to whole project"],
    "questions": ["Clarifying question 1?"]
}

EDGE TYPES (match Graph.html):
- "data": Data flow between components (green)
- "api": API calls or events (blue)
- "auth": Authentication/security (red)
- "schema": Schema/structure definitions (yellow)
- "log": Logging connections (gray)

STATUS OPTIONS:
- "pending": Not started
- "active": Currently being worked on
- "complete": Finished

Be thorough but concise. Identify 3-8 core components for most projects.
```

### interviewer.py

```python
"""
Interviewer Agent - Phase 1 of the orchestration pipeline.
Analyzes user input and creates structured project briefs.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from .base_agent import BaseAgent
from db import Database, Project, Component

class InterviewerAgent(BaseAgent):
    """
    Conducts project interviews and generates structured briefs.

    Scope: User conversation only
    Inputs: User's project description
    Outputs: Structured project brief (JSON)
    """

    def __init__(self, db: Database):
        super().__init__(
            agent_id=f"interviewer_{uuid.uuid4().hex[:8]}",
            agent_type="interviewer",
            db=db
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
        response = self.call_claude(
            prompt=f"Analyze this project description and create a structured brief:\n\n{user_prompt}",
            system=system_prompt,
            expect_json=True
        )

        # Parse the response
        try:
            brief = self.parse_json_response(response)
        except ValueError as e:
            self.log('error', f'Failed to parse response: {e}')
            # Return minimal structure on parse failure
            brief = self._fallback_brief(user_prompt)

        # Validate and enhance the brief
        brief = self._validate_brief(brief, user_prompt)

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
            "questions": []
        }

        for key, default in defaults.items():
            if key not in brief or brief[key] is None:
                brief[key] = default

        # Ensure components have required Graph.html fields
        for i, comp in enumerate(brief.get("components", [])):
            comp.setdefault("id", f"comp_{i}")
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
            comp.setdefault("testCases", [])

        # Add root node if not present
        has_root = any(c.get("type") == "root" for c in brief["components"])
        if not has_root and brief["components"]:
            root_node = {
                "id": "ROOT",
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
                    "from": "ROOT",
                    "to": brief["components"][1]["id"],
                    "label": "Initiates",
                    "type": "data"
                })

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
        import json

        # Create or update project
        if project_id:
            project = self.db.get_project(project_id)
            if project:
                self.db.update_project(project_id, {
                    'name': brief['title'],
                    'summary': brief['summary'],
                    'problem': brief['problem'],
                    'phase': 'interview'
                })
            else:
                project_id = None

        if not project_id:
            project_id = f"proj_{uuid.uuid4().hex[:8]}"
            project = self.db.create_project(
                id=project_id,
                name=brief['title'],
                summary=brief['summary'],
                problem=brief['problem'],
                phase='interview'
            )

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

        # Save edges
        for edge in brief.get('edges', []):
            self.db.create_edge(
                project_id=project_id,
                from_id=edge['from'],
                to_id=edge['to'],
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

        return self.db.get_project(project_id)

    def to_graph_data(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Convert brief to Graph.html format."""
        return {
            "projectName": brief.get("title", "Untitled"),
            "projectSummary": brief.get("summary", ""),
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
                {"id": "INT", "name": "Interviewer", "dept": "DISC", "initials": "IN", "status": "complete"}
            ],
            "nodes": brief.get("components", []),
            "edges": brief.get("edges", []),
            "timestamp": datetime.now().isoformat()
        }
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] InterviewerAgent class extends BaseAgent correctly
- [ ] `execute()` successfully calls Claude API
- [ ] Response is parsed into valid JSON
- [ ] Brief contains all required fields (title, summary, components, edges)
- [ ] Components have all Graph.html required fields
- [ ] Root node is automatically added if missing
- [ ] Edges connect components correctly
- [ ] Brief is saved to database
- [ ] `to_graph_data()` produces valid Graph.html format
- [ ] Dashboard renders the generated data
- [ ] Works for simple project descriptions (1 component)
- [ ] Works for complex project descriptions (5+ components)
- [ ] Handles edge cases gracefully (empty input, very long input)

## Tests Required

### test_interviewer.py

```python
import pytest
from unittest.mock import Mock, patch
from agents.interviewer import InterviewerAgent
from db import Database

class TestInterviewerAgent:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / 'test.db'))

    @pytest.fixture
    def agent(self, db):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            with patch('anthropic.Anthropic'):
                return InterviewerAgent(db)

    def test_scoped_context(self, agent):
        """Interviewer has correct scope restrictions"""
        ctx = agent.get_scoped_context()
        assert ctx['role'] == 'interviewer'
        assert 'no_existing_code' in ctx['restrictions']

    def test_simple_project(self, agent):
        """Analyzes simple project description"""
        # Mock Claude response
        mock_response = '''
        {
            "title": "Todo App",
            "summary": "A simple todo application",
            "problem": "Need to track tasks",
            "goals": ["Track todos", "Mark complete"],
            "components": [
                {"id": "ui", "label": "UI", "type": "node"},
                {"id": "storage", "label": "Storage", "type": "node"}
            ],
            "edges": [{"from": "ui", "to": "storage", "type": "data"}]
        }
        '''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            brief = agent.execute("Build a todo app")

        assert brief['title'] == 'Todo App'
        assert len(brief['components']) >= 2  # +1 for auto-added root

    def test_adds_root_node(self, agent):
        """Automatically adds root node if missing"""
        mock_response = '''
        {
            "title": "Test",
            "summary": "Test project",
            "components": [{"id": "c1", "label": "C1", "type": "node"}],
            "edges": []
        }
        '''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            brief = agent.execute("Test project")

        # Should have root + original component
        assert len(brief['components']) == 2
        assert brief['components'][0]['type'] == 'root'
        assert brief['components'][0]['id'] == 'ROOT'

    def test_graph_data_format(self, agent):
        """Produces valid Graph.html format"""
        mock_response = '''{"title": "Test", "summary": "Test", "components": [], "edges": []}'''

        with patch.object(agent, 'call_claude', return_value=mock_response):
            brief = agent.execute("Test")
            graph_data = agent.to_graph_data(brief)

        assert 'projectName' in graph_data
        assert 'globalTasks' in graph_data
        assert 'nodes' in graph_data
        assert 'edges' in graph_data
        assert 'agents' in graph_data

    def test_saves_to_database(self, agent, db):
        """Brief is persisted to database"""
        mock_response = '''
        {
            "title": "DB Test",
            "summary": "Testing database save",
            "components": [{"id": "c1", "label": "C1", "type": "node"}],
            "edges": []
        }
        '''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            brief = agent.execute("DB test")

        # Verify project saved
        project = db.get_project(brief['project_id'])
        assert project is not None
        assert project.name == 'DB Test'

    def test_complex_project(self, agent):
        """Handles complex multi-component project"""
        mock_response = '''
        {
            "title": "E-Commerce Platform",
            "summary": "Full-stack e-commerce",
            "problem": "Need online store",
            "goals": ["Sell products", "Process payments"],
            "components": [
                {"id": "frontend", "label": "Frontend", "type": "node"},
                {"id": "api", "label": "API", "type": "node"},
                {"id": "db", "label": "Database", "type": "node"},
                {"id": "payment", "label": "Payment", "type": "node"},
                {"id": "inventory", "label": "Inventory", "type": "node"}
            ],
            "edges": [
                {"from": "frontend", "to": "api", "type": "api"},
                {"from": "api", "to": "db", "type": "data"},
                {"from": "api", "to": "payment", "type": "auth"},
                {"from": "api", "to": "inventory", "type": "data"}
            ],
            "global_requirements": ["PCI compliance", "99.9% uptime"],
            "global_risks": ["Payment fraud", "Data breach"]
        }
        '''
        with patch.object(agent, 'call_claude', return_value=mock_response):
            brief = agent.execute("Build an e-commerce platform")

        assert len(brief['components']) >= 5
        assert len(brief['edges']) >= 4

    def test_fallback_on_parse_error(self, agent):
        """Returns fallback brief when parsing fails"""
        with patch.object(agent, 'call_claude', return_value='Invalid JSON {{{'):
            brief = agent.execute("Test project")

        # Should get fallback structure
        assert brief['title'] == 'New Project'
        assert 'questions' in brief
```

## Conversational Interview Feature

The Interviewer Agent supports multi-turn refinement through clarifying questions.

### How It Works

```
User Input → Initial Analysis → Questions Generated
                                      ↓
User Answers → Refine Analysis → More Questions OR Ready for Design
                  ↑___________________|
              (loop until requirements are clear)
```

### Key Methods

#### `refine(original_brief, answers, additional_context)`

Refines an existing brief based on user answers to clarifying questions.

```python
# Example usage
interviewer = InterviewerAgent(db)
brief = interviewer.execute("Build an app")  # Initial analysis

# If questions were generated
if brief.get('questions'):
    answers = {
        "What type of application?": "Web application",
        "Who is the target audience?": "Small businesses"
    }
    refined_brief = interviewer.refine(brief, answers, "Should support multiple languages")
```

#### `is_ready_for_design(brief)`

Checks if the brief is complete enough to proceed:
- No critical questions remain
- At least 2 components identified
- Has clear goals

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/start_interview` | POST | Initial project analysis |
| `/api/refine_interview` | POST | Refine with answers |

### Interview.html Flow

1. **Phase 1: Describe** - User enters project description
2. **Phase 2: Clarify** - Shows questions, collects answers, refines
3. **Phase 3: Review** - Ready for design, shows final components

### Graph Data Format Additions

```javascript
{
    "projectName": "...",
    "projectSummary": "...",
    "questions": ["Question 1?", "Question 2?"],  // NEW
    "readyForDesign": true,                        // NEW
    "refinementIteration": 2,                      // NEW
    // ... rest of graph data
}
```

---

## Integration with Existing Code

### Update agent_logic.py

```python
# Replace current implementation with:
from agents.interviewer import InterviewerAgent
from db import Database

def generate_graph(user_prompt):
    db = Database()
    interviewer = InterviewerAgent(db)
    brief = interviewer.execute(user_prompt)
    return interviewer.to_graph_data(brief)
```

### Update server.py

```python
# In do_POST for /api/start_interview
from agents.interviewer import InterviewerAgent
from db import Database

db = Database()
interviewer = InterviewerAgent(db)
brief = interviewer.execute(user_prompt)
graph_data = interviewer.to_graph_data(brief)
```

---

*Status: Pending*
*Estimated Complexity: High*
*Dependencies: 1.1 Database Setup, 1.2 Claude API Integration*
