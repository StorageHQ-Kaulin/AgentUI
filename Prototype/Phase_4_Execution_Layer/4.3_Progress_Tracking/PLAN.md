# 4.3 Progress Tracking

## Objective

Implement real-time progress tracking that updates the database and dashboard as workers execute tasks. Enable the Graph.html terminal UI to show live execution status.

## Files to Create

```
Visual/
├── tracking/
│   ├── __init__.py
│   ├── progress_tracker.py   # Progress tracking service
│   └── event_emitter.py      # Event emission for UI updates
├── api/
│   └── websocket.py          # WebSocket for real-time updates (optional)
```

## Implementation

### tracking/progress_tracker.py

```python
"""
Progress Tracker - Real-time task execution tracking.
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
import threading

from db import Database

@dataclass
class ExecutionEvent:
    """Single execution event for logging."""
    timestamp: str
    event_type: str  # 'start', 'action', 'progress', 'complete', 'error'
    message: str
    details: Optional[Dict] = None

@dataclass
class TaskProgress:
    """Progress state for a single task."""
    task_id: str
    agent_id: str
    status: str = 'pending'
    iteration: int = 0
    max_iterations: int = 20
    progress_percent: int = 0
    criteria_verified: int = 0
    criteria_total: int = 0
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    cost_estimate: float = 0.0
    events: List[ExecutionEvent] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/UI."""
        return {
            'taskId': self.task_id,
            'agentId': self.agent_id,
            'status': self.status,
            'iteration': self.iteration,
            'maxIterations': self.max_iterations,
            'progress': self.progress_percent,
            'criteriaVerified': self.criteria_verified,
            'criteriaTotal': self.criteria_total,
            'filesCreated': self.files_created,
            'filesModified': self.files_modified,
            'cost': self.cost_estimate,
            'logs': [
                {'time': e.timestamp.split('T')[1][:8], 'message': e.message}
                for e in self.events[-10:]  # Last 10 events
            ],
            'startedAt': self.started_at,
            'completedAt': self.completed_at
        }

    def to_graph_ui(self) -> Dict[str, Any]:
        """Convert to Graph.html renderAgentControl format."""
        return {
            'sessionId': f'sess_{self.task_id}',
            'iteration': self.iteration,
            'maxIterations': self.max_iterations,
            'cost': self.cost_estimate,
            'maxCost': 10.00,
            'progress': self.progress_percent,
            'criteria': [
                {'text': f'Criterion {i+1}', 'status': 'pass' if i < self.criteria_verified else 'pending'}
                for i in range(self.criteria_total)
            ],
            'logs': [
                {'time': e.timestamp.split('T')[1][:8], 'message': e.message}
                for e in self.events[-5:]
            ],
            'status': self.status
        }

class ProgressTracker:
    """
    Tracks and broadcasts task execution progress.
    """

    def __init__(self, db: Database):
        self.db = db
        self._tasks: Dict[str, TaskProgress] = {}
        self._listeners: List[Callable] = []
        self._lock = threading.Lock()

    def start_task(self, task_id: str, agent_id: str, criteria_total: int) -> TaskProgress:
        """Initialize tracking for a task."""
        with self._lock:
            progress = TaskProgress(
                task_id=task_id,
                agent_id=agent_id,
                status='in_progress',
                criteria_total=criteria_total,
                started_at=datetime.now().isoformat()
            )
            progress.events.append(ExecutionEvent(
                timestamp=datetime.now().isoformat(),
                event_type='start',
                message='Task execution started'
            ))
            self._tasks[task_id] = progress
            self._notify(progress)
            self._persist(progress)
            return progress

    def update_iteration(self, task_id: str, iteration: int):
        """Update iteration count."""
        with self._lock:
            if task_id in self._tasks:
                progress = self._tasks[task_id]
                progress.iteration = iteration
                self._notify(progress)

    def update_progress(self, task_id: str, percent: int):
        """Update progress percentage."""
        with self._lock:
            if task_id in self._tasks:
                progress = self._tasks[task_id]
                progress.progress_percent = percent
                self._notify(progress)

    def verify_criterion(self, task_id: str, criterion_index: int):
        """Mark a criterion as verified."""
        with self._lock:
            if task_id in self._tasks:
                progress = self._tasks[task_id]
                progress.criteria_verified = criterion_index + 1
                progress.progress_percent = int(
                    (progress.criteria_verified / progress.criteria_total) * 100
                )
                progress.events.append(ExecutionEvent(
                    timestamp=datetime.now().isoformat(),
                    event_type='progress',
                    message=f'Criterion {criterion_index + 1} verified'
                ))
                self._notify(progress)
                self._persist(progress)

    def log_action(self, task_id: str, action: str, target: str, success: bool):
        """Log an action taken by the agent."""
        with self._lock:
            if task_id in self._tasks:
                progress = self._tasks[task_id]
                status = '✓' if success else '✗'
                progress.events.append(ExecutionEvent(
                    timestamp=datetime.now().isoformat(),
                    event_type='action',
                    message=f'{status} {action}: {target}',
                    details={'action': action, 'target': target, 'success': success}
                ))

                # Track files
                if action in ('write', 'create') and success:
                    progress.files_created.append(target)
                elif action == 'edit' and success:
                    progress.files_modified.append(target)

                self._notify(progress)

    def log_error(self, task_id: str, error: str):
        """Log an error."""
        with self._lock:
            if task_id in self._tasks:
                progress = self._tasks[task_id]
                progress.events.append(ExecutionEvent(
                    timestamp=datetime.now().isoformat(),
                    event_type='error',
                    message=f'ERROR: {error}'
                ))
                self._notify(progress)

    def complete_task(self, task_id: str, success: bool):
        """Mark task as complete."""
        with self._lock:
            if task_id in self._tasks:
                progress = self._tasks[task_id]
                progress.status = 'complete' if success else 'failed'
                progress.completed_at = datetime.now().isoformat()
                progress.events.append(ExecutionEvent(
                    timestamp=datetime.now().isoformat(),
                    event_type='complete',
                    message=f'Task {"completed successfully" if success else "failed"}'
                ))
                self._notify(progress)
                self._persist(progress)

    def get_progress(self, task_id: str) -> Optional[TaskProgress]:
        """Get current progress for a task."""
        return self._tasks.get(task_id)

    def get_all_active(self) -> List[TaskProgress]:
        """Get all active task progress."""
        return [p for p in self._tasks.values() if p.status == 'in_progress']

    def add_listener(self, callback: Callable[[TaskProgress], None]):
        """Add a progress update listener."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, progress: TaskProgress):
        """Notify all listeners of progress update."""
        for listener in self._listeners:
            try:
                listener(progress)
            except Exception as e:
                print(f"Listener error: {e}")

    def _persist(self, progress: TaskProgress):
        """Persist progress to database."""
        try:
            self.db.update_task(progress.task_id, {
                'status': progress.status,
                'iterations_used': progress.iteration
            })

            # Log to database
            self.db.create_log(
                task_id=progress.task_id,
                agent_id=progress.agent_id,
                action='progress_update',
                message=json.dumps(progress.to_dict()),
                level='info'
            )
        except Exception as e:
            print(f"Persist error: {e}")
```

### api/websocket.py (Optional Enhancement)

```python
"""
WebSocket server for real-time progress updates.
"""
import asyncio
import json
from typing import Set
import websockets

from tracking.progress_tracker import ProgressTracker, TaskProgress

class ProgressWebSocket:
    """WebSocket server for broadcasting progress updates."""

    def __init__(self, tracker: ProgressTracker, host: str = 'localhost', port: int = 8765):
        self.tracker = tracker
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()

        # Register as tracker listener
        tracker.add_listener(self._on_progress)

    async def start(self):
        """Start the WebSocket server."""
        async with websockets.serve(self._handler, self.host, self.port):
            print(f"Progress WebSocket server started on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever

    async def _handler(self, websocket, path):
        """Handle WebSocket connections."""
        self.clients.add(websocket)
        try:
            async for message in websocket:
                # Handle incoming messages if needed
                pass
        finally:
            self.clients.remove(websocket)

    def _on_progress(self, progress: TaskProgress):
        """Broadcast progress update to all clients."""
        if self.clients:
            message = json.dumps({
                'type': 'progress',
                'data': progress.to_dict()
            })
            asyncio.create_task(self._broadcast(message))

    async def _broadcast(self, message: str):
        """Send message to all connected clients."""
        if self.clients:
            await asyncio.gather(
                *[client.send(message) for client in self.clients],
                return_exceptions=True
            )
```

## Dashboard Integration

Add to Graph.html for real-time updates:

```javascript
// Connect to progress WebSocket
let progressSocket = null;

function connectProgressSocket(projectId) {
    progressSocket = new WebSocket('ws://localhost:8765');

    progressSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
            updateAgentPanel(data.data);
        }
    };

    progressSocket.onclose = () => {
        // Reconnect after delay
        setTimeout(() => connectProgressSocket(projectId), 3000);
    };
}

function updateAgentPanel(progress) {
    const panelContainer = document.getElementById('db-agent-panel');
    if (panelContainer) {
        panelContainer.innerHTML = UI.renderAgentControl({
            label: `Task ${progress.taskId}`,
            ...progress
        }, progress.agentId);
    }
}
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] ProgressTracker initializes with database
- [ ] `start_task()` creates progress record
- [ ] `update_iteration()` updates count
- [ ] `verify_criterion()` tracks criteria progress
- [ ] `log_action()` records actions
- [ ] `log_error()` records errors
- [ ] `complete_task()` finalizes progress
- [ ] Listeners receive progress updates
- [ ] Progress persists to database
- [ ] `to_graph_ui()` matches Graph.html format
- [ ] Dashboard receives real-time updates (polling or WebSocket)
- [ ] Multiple concurrent tasks track independently

## Tests Required

### test_progress_tracker.py

```python
import pytest
from tracking.progress_tracker import ProgressTracker, TaskProgress, ExecutionEvent
from db import Database

class TestProgressTracker:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / 'test.db'))

    @pytest.fixture
    def tracker(self, db):
        return ProgressTracker(db)

    def test_start_task(self, tracker):
        """Starts tracking a task."""
        progress = tracker.start_task('task_1', 'agent_1', criteria_total=3)

        assert progress.task_id == 'task_1'
        assert progress.status == 'in_progress'
        assert progress.criteria_total == 3

    def test_verify_criterion(self, tracker):
        """Verifying criteria updates progress."""
        tracker.start_task('task_1', 'agent_1', criteria_total=4)

        tracker.verify_criterion('task_1', 0)
        progress = tracker.get_progress('task_1')

        assert progress.criteria_verified == 1
        assert progress.progress_percent == 25

    def test_complete_task(self, tracker):
        """Completing task updates status."""
        tracker.start_task('task_1', 'agent_1', criteria_total=2)
        tracker.complete_task('task_1', success=True)

        progress = tracker.get_progress('task_1')
        assert progress.status == 'complete'
        assert progress.completed_at is not None

    def test_listener_notification(self, tracker):
        """Listeners receive updates."""
        updates = []
        tracker.add_listener(lambda p: updates.append(p))

        tracker.start_task('task_1', 'agent_1', criteria_total=1)
        tracker.verify_criterion('task_1', 0)

        assert len(updates) == 2  # start + verify

    def test_to_graph_ui_format(self, tracker):
        """Output matches Graph.html format."""
        tracker.start_task('task_1', 'agent_1', criteria_total=3)
        progress = tracker.get_progress('task_1')
        ui_data = progress.to_graph_ui()

        assert 'sessionId' in ui_data
        assert 'iteration' in ui_data
        assert 'progress' in ui_data
        assert 'criteria' in ui_data
        assert 'logs' in ui_data
        assert 'status' in ui_data
```

---

*Status: Pending*
*Estimated Complexity: Medium*
*Dependencies: 4.1, 4.2, 2.3 Dashboard Integration*
