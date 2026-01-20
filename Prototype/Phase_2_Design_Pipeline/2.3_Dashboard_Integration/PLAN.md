# 2.3 Dashboard Integration

## Objective

Connect the Dashboard (Graph.html) to the SQLite database for real-time data. Replace static JSON file loading with API-driven database queries.

## Files to Modify/Create

```
Visual/
├── server.py                 # Update API endpoints
├── api/
│   ├── __init__.py
│   ├── routes.py             # API route handlers
│   └── serializers.py        # Database to JSON conversion
├── Dashboard.html            # Update to use new API
└── Graph.html                # Update data loading
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/:id` | Get project details |
| GET | `/api/projects/:id/graph` | Get Graph.html formatted data |
| PATCH | `/api/projects/:id` | Update project |
| POST | `/api/projects/:id/approve` | Approve design (move to next phase) |
| GET | `/api/components/:id` | Get component details |
| PATCH | `/api/components/:id` | Update component |
| POST | `/api/components/:id/files` | Attach file to component |

## Implementation

### api/serializers.py

```python
"""
Serializers to convert database models to Graph.html format.
"""
from typing import Dict, Any, List
from db import Database

class GraphSerializer:
    """Converts database data to Graph.html format."""

    def __init__(self, db: Database):
        self.db = db

    def serialize_project(self, project_id: str) -> Dict[str, Any]:
        """
        Serialize a project to full Graph.html format.

        Matches the structure expected by Graph.html:
        - projectName
        - projectSummary
        - globalTasks
        - agents
        - nodes (components)
        - edges
        """
        project = self.db.get_project(project_id)
        if not project:
            return None

        components = self.db.get_components(project_id)
        edges = self.db.get_edges(project_id)
        global_tasks = self.db.get_global_tasks(project_id)
        agents = self.db.get_agents_for_project(project_id)

        return {
            "projectName": project.name,
            "projectSummary": project.summary or "",
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
        """Serialize a single component to Graph.html node format."""
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
```

### api/routes.py

```python
"""
API routes for the orchestrator dashboard.
"""
import json
from typing import Optional
from db import Database
from .serializers import GraphSerializer

class APIHandler:
    def __init__(self, db: Database):
        self.db = db
        self.serializer = GraphSerializer(db)

    def get_projects(self) -> dict:
        """List all projects."""
        projects = self.db.get_all_projects()
        return {
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "phase": p.phase,
                    "updated_at": p.updated_at
                }
                for p in projects
            ]
        }

    def get_project_graph(self, project_id: str) -> Optional[dict]:
        """Get project in Graph.html format."""
        return self.serializer.serialize_project(project_id)

    def update_component(self, component_id: str, updates: dict) -> dict:
        """Update a component."""
        # Filter allowed updates
        allowed_fields = {
            'x', 'y', 'status', 'summary', 'problem',
            'goals', 'scope', 'requirements', 'risks'
        }
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}

        self.db.update_component(component_id, filtered)
        return {"status": "success", "updated": list(filtered.keys())}

    def attach_file(self, component_id: str, file_path: str) -> dict:
        """Attach a file to a component."""
        comp = self.db.get_component(component_id)
        if not comp:
            return {"status": "error", "message": "Component not found"}

        files = comp.files or []
        files.append({"name": file_path.split('/')[-1], "path": file_path, "type": "file"})

        self.db.update_component(component_id, {"files": files})
        return {"status": "success", "files": files}

    def approve_design(self, project_id: str) -> dict:
        """Approve design and advance to next phase."""
        project = self.db.get_project(project_id)
        if not project:
            return {"status": "error", "message": "Project not found"}

        # Update phase
        phase_order = ['interview', 'design', 'visualize', 'planning', 'breakdown', 'assign', 'execute']
        current_idx = phase_order.index(project.phase) if project.phase in phase_order else 0
        next_phase = phase_order[min(current_idx + 1, len(phase_order) - 1)]

        self.db.update_project(project_id, {'phase': next_phase})

        # Update global tasks
        self.db.mark_global_task_done(project_id, f"Phase {current_idx + 1}")

        return {"status": "success", "new_phase": next_phase}
```

### Updated server.py

```python
# Add to existing server.py

from api.routes import APIHandler
from db import Database

db = Database()
api = APIHandler(db)

class AgenticHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)

        # API: List projects
        if parsed_path.path == '/api/projects':
            self.send_json(api.get_projects())
            return

        # API: Get project graph data
        if parsed_path.path.startswith('/api/projects/') and parsed_path.path.endswith('/graph'):
            project_id = parsed_path.path.split('/')[3]
            data = api.get_project_graph(project_id)
            if data:
                self.send_json(data)
            else:
                self.send_json({'error': 'Project not found'}, 404)
            return

        # ... existing routes ...

    def do_PATCH(self):
        parsed_path = urllib.parse.urlparse(self.path)

        # API: Update component
        if parsed_path.path.startswith('/api/components/'):
            component_id = parsed_path.path.split('/')[3]
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))
            result = api.update_component(component_id, body)
            self.send_json(result)
            return
```

### Graph.html Updates

```javascript
// Replace static ProjectData with API fetch

const API_BASE = '';

async function loadProjectData(projectId) {
    try {
        const response = await fetch(`${API_BASE}/api/projects/${projectId}/graph`);
        if (!response.ok) throw new Error('Failed to load project');
        return await response.json();
    } catch (error) {
        console.error('Error loading project:', error);
        return null;
    }
}

// Initialize with API data
async function initWithProject(projectId) {
    const data = await loadProjectData(projectId);
    if (data) {
        State.graphNodes = data.nodes || [];
        State.graphEdges = data.edges || [];
        State.agents = data.agents || [];
        // ... update GlobalTasks, etc.
        UI.renderGraph();
        UI.renderGlobalTasks();
    }
}

// Update node position via API
async function updateNodePosition(nodeId, x, y) {
    try {
        await fetch(`${API_BASE}/api/components/${nodeId}`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({x, y})
        });
    } catch (error) {
        console.error('Error saving position:', error);
    }
}
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] `/api/projects` returns list of all projects
- [ ] `/api/projects/:id/graph` returns Graph.html format
- [ ] Data matches Graph.html expected structure exactly
- [ ] Components include metrics and testCases
- [ ] Edges include correct types
- [ ] GlobalTasks reflect database state
- [ ] Graph.html renders data from API
- [ ] Node drag updates persist to database
- [ ] File attachments save to database
- [ ] Design approval advances project phase
- [ ] Real-time updates work (or polling fallback)

## Tests Required

### test_dashboard_api.py

```python
import pytest
import json
from db import Database
from api.routes import APIHandler
from api.serializers import GraphSerializer

class TestDashboardAPI:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / 'test.db'))

    @pytest.fixture
    def api(self, db):
        return APIHandler(db)

    @pytest.fixture
    def project_with_data(self, db):
        """Create project with components."""
        db.create_project('proj1', 'Test Project', summary='Test')
        db.create_component('ROOT', 'proj1', 'Test Project', type='root', x=500, y=50)
        db.create_component('comp1', 'proj1', 'Component 1', x=500, y=200)
        db.create_edge('proj1', 'ROOT', 'comp1', 'Initiates', 'data')
        db.create_global_task('proj1', 'Phase 1', done=True)
        return 'proj1'

    def test_list_projects(self, api, project_with_data):
        """Lists all projects."""
        result = api.get_projects()
        assert len(result['projects']) >= 1
        assert result['projects'][0]['id'] == 'proj1'

    def test_get_project_graph(self, api, project_with_data):
        """Returns Graph.html format."""
        data = api.get_project_graph('proj1')

        assert data['projectName'] == 'Test Project'
        assert len(data['nodes']) == 2
        assert len(data['edges']) == 1
        assert data['edges'][0]['type'] == 'data'
        assert len(data['globalTasks']) >= 1

    def test_node_has_graph_fields(self, api, project_with_data):
        """Nodes have all Graph.html fields."""
        data = api.get_project_graph('proj1')
        node = data['nodes'][0]

        required_fields = [
            'id', 'label', 'x', 'y', 'type', 'status',
            'summary', 'goals', 'scope', 'requirements',
            'risks', 'inputs', 'outputs', 'files', 'subtasks',
            'metrics', 'testCases'
        ]
        for field in required_fields:
            assert field in node, f"Missing field: {field}"

    def test_update_component(self, api, project_with_data, db):
        """Updates component in database."""
        result = api.update_component('comp1', {'x': 600, 'y': 300})
        assert result['status'] == 'success'

        comp = db.get_component('comp1')
        assert comp.x == 600
        assert comp.y == 300

    def test_attach_file(self, api, project_with_data, db):
        """Attaches file to component."""
        result = api.attach_file('comp1', 'src/app.py')
        assert result['status'] == 'success'

        comp = db.get_component('comp1')
        assert any(f['path'] == 'src/app.py' for f in comp.files)

    def test_approve_design(self, api, project_with_data, db):
        """Advances project phase."""
        db.update_project('proj1', {'phase': 'design'})

        result = api.approve_design('proj1')
        assert result['status'] == 'success'
        assert result['new_phase'] == 'visualize'
```

---

*Status: Pending*
*Estimated Complexity: Medium*
*Dependencies: 1.1 Database Setup, 2.1 Architect Agent*
