# 4.1 Worker Agent Framework

## Objective

Create a Worker agent framework that can execute tasks with tool access (read files, write files, run commands) while maintaining scoped context isolation.

## Files to Create

```
Visual/
├── agents/
│   ├── worker.py             # Worker agent class
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── file_reader.py    # Read file contents
│   │   ├── file_writer.py    # Write/create files
│   │   ├── shell.py          # Execute commands
│   │   └── verifier.py       # Verify acceptance criteria
│   └── prompts/
│       └── worker.txt        # Worker system prompt
```

## Implementation

### prompts/worker.txt

```
You are a Worker agent executing a specific task. You have access to tools for reading files, writing files, and running commands.

YOUR TASK:
{task_prompt}

AVAILABLE TOOLS:
- read_file(path): Read file contents
- write_file(path, content): Create or overwrite file
- edit_file(path, old, new): Replace text in file
- run_command(cmd): Execute shell command
- verify_criterion(index): Mark acceptance criterion as verified

EXECUTION RULES:
1. Read existing files before modifying
2. Create parent directories before writing files
3. Verify each acceptance criterion as you complete it
4. Report errors immediately
5. Stay within your task scope - don't modify unrelated files

OUTPUT FORMAT:
After each action, report:
{
    "action": "read|write|command|verify",
    "target": "file path or command",
    "result": "success|error",
    "message": "details"
}

When task is complete:
{
    "status": "complete",
    "files_created": ["list", "of", "files"],
    "files_modified": ["list"],
    "criteria_verified": [0, 1, 2]
}

If blocked:
{
    "status": "blocked",
    "reason": "description of blocker",
    "needs": "what is needed to proceed"
}
```

### tools/file_reader.py

```python
"""File reading tool for Worker agents."""
import os
from typing import Optional

class FileReader:
    """Safely read files within allowed scope."""

    def __init__(self, allowed_paths: list[str]):
        self.allowed_paths = [os.path.abspath(p) for p in allowed_paths]

    def read(self, path: str, max_lines: int = 500) -> dict:
        """
        Read a file's contents.

        Args:
            path: Path to file
            max_lines: Maximum lines to return

        Returns:
            {success: bool, content: str, lines: int, error: str}
        """
        abs_path = os.path.abspath(path)

        # Check if path is allowed
        if not self._is_allowed(abs_path):
            return {
                'success': False,
                'content': '',
                'error': f'Path not in allowed scope: {path}'
            }

        if not os.path.exists(abs_path):
            return {
                'success': False,
                'content': '',
                'error': f'File not found: {path}'
            }

        try:
            with open(abs_path, 'r', errors='replace') as f:
                lines = f.readlines()

            if len(lines) > max_lines:
                content = ''.join(lines[:max_lines])
                content += f'\n... (truncated, {len(lines) - max_lines} more lines)'
            else:
                content = ''.join(lines)

            return {
                'success': True,
                'content': content,
                'lines': len(lines),
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'content': '',
                'error': str(e)
            }

    def _is_allowed(self, path: str) -> bool:
        """Check if path is within allowed directories."""
        for allowed in self.allowed_paths:
            if path.startswith(allowed):
                return True
        return False
```

### tools/file_writer.py

```python
"""File writing tool for Worker agents."""
import os
from typing import Optional

class FileWriter:
    """Safely write files within allowed scope."""

    def __init__(self, allowed_paths: list[str]):
        self.allowed_paths = [os.path.abspath(p) for p in allowed_paths]

    def write(self, path: str, content: str, create_dirs: bool = True) -> dict:
        """
        Write content to a file.

        Args:
            path: Path to file
            content: Content to write
            create_dirs: Create parent directories if needed

        Returns:
            {success: bool, error: str}
        """
        abs_path = os.path.abspath(path)

        if not self._is_allowed(abs_path):
            return {
                'success': False,
                'error': f'Path not in allowed scope: {path}'
            }

        try:
            if create_dirs:
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)

            with open(abs_path, 'w') as f:
                f.write(content)

            return {
                'success': True,
                'error': None,
                'bytes_written': len(content)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def edit(self, path: str, old: str, new: str) -> dict:
        """
        Replace text in a file.

        Args:
            path: Path to file
            old: Text to replace
            new: Replacement text

        Returns:
            {success: bool, replacements: int, error: str}
        """
        abs_path = os.path.abspath(path)

        if not self._is_allowed(abs_path):
            return {
                'success': False,
                'error': f'Path not in allowed scope: {path}'
            }

        if not os.path.exists(abs_path):
            return {
                'success': False,
                'error': f'File not found: {path}'
            }

        try:
            with open(abs_path, 'r') as f:
                content = f.read()

            count = content.count(old)
            if count == 0:
                return {
                    'success': False,
                    'replacements': 0,
                    'error': 'Old text not found in file'
                }

            new_content = content.replace(old, new)

            with open(abs_path, 'w') as f:
                f.write(new_content)

            return {
                'success': True,
                'replacements': count,
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'replacements': 0,
                'error': str(e)
            }

    def _is_allowed(self, path: str) -> bool:
        """Check if path is within allowed directories."""
        for allowed in self.allowed_paths:
            if path.startswith(allowed):
                return True
        return False
```

### worker.py

```python
"""
Worker Agent - Executes tasks with tool access.
"""
from typing import Dict, Any, List, Optional
import uuid
import json

from .base_agent import BaseAgent
from .tools.file_reader import FileReader
from .tools.file_writer import FileWriter
from schemas.task import Task, TaskStatus
from db import Database

class WorkerAgent(BaseAgent):
    """
    Executes tasks using Claude with tool access.

    Scope: Single task only
    Inputs: Task details, relevant file contents
    Outputs: Completed work, status updates
    """

    def __init__(self, db: Database, task_id: str, project_root: str):
        super().__init__(
            agent_id=f"worker_{task_id}_{uuid.uuid4().hex[:6]}",
            agent_type="worker",
            db=db
        )
        self.task_id = task_id
        self.project_root = project_root

        # Initialize tools with scoped access
        self.file_reader = FileReader([project_root])
        self.file_writer = FileWriter([project_root])

        # Load task
        self.task_record = db.get_task(task_id)
        self.task = self.task_record.to_task() if self.task_record else None

        # Execution state
        self.iteration = 0
        self.max_iterations = 20
        self.actions_log = []

    def get_scoped_context(self) -> Dict[str, Any]:
        """Worker sees only its task."""
        return {
            "role": "worker",
            "task_id": self.task_id,
            "access": ["task_files", "task_scope"],
            "restrictions": ["no_other_tasks", "no_manager_data"]
        }

    def execute(self) -> Dict[str, Any]:
        """
        Execute the task.

        Returns:
            Execution result with status
        """
        if not self.task:
            return {'status': 'error', 'message': 'Task not found'}

        self.log('start', f'Executing task: {self.task.title}')

        # Update task status
        self.db.update_task(self.task_id, {
            'status': 'in_progress',
            'assigned_agent': self.agent_id
        })

        try:
            result = self._execution_loop()
        except Exception as e:
            self.log('error', str(e))
            result = {'status': 'failed', 'error': str(e)}
            self.db.update_task(self.task_id, {'status': 'failed', 'error': str(e)})

        return result

    def _execution_loop(self) -> Dict[str, Any]:
        """Main execution loop."""
        while self.iteration < self.max_iterations:
            self.iteration += 1
            self.log('iteration', f'Starting iteration {self.iteration}')

            # Build prompt with task and context
            prompt = self._build_execution_prompt()

            # Call Claude
            response = self.call_claude(
                prompt=prompt,
                system=self.get_system_prompt(),
                expect_json=False  # Worker may output mixed content
            )

            # Parse and execute actions from response
            actions = self._parse_actions(response)

            for action in actions:
                result = self._execute_action(action)
                self.actions_log.append(result)

                # Check for completion or blocking
                if result.get('status') == 'complete':
                    self._mark_complete()
                    return {'status': 'complete', 'iterations': self.iteration}
                elif result.get('status') == 'blocked':
                    return {'status': 'blocked', 'reason': result.get('reason')}

            # Check if all criteria verified
            if self._all_criteria_verified():
                self._mark_complete()
                return {'status': 'complete', 'iterations': self.iteration}

        # Max iterations reached
        return {'status': 'incomplete', 'iterations': self.iteration, 'reason': 'Max iterations'}

    def _build_execution_prompt(self) -> str:
        """Build prompt with task context."""
        prompt = self.task.to_agent_prompt()

        # Add file contents for files_to_read
        prompt += "\n\nCURRENT FILE CONTENTS:\n"
        for file_ref in self.task.files_to_read:
            result = self.file_reader.read(file_ref.path)
            if result['success']:
                prompt += f"\n--- {file_ref.path} ---\n{result['content']}\n"

        prompt += f"\n\nITERATION: {self.iteration}/{self.max_iterations}\n"
        prompt += "\nWhat is your next action?"

        return prompt

    def _parse_actions(self, response: str) -> List[Dict]:
        """Parse actions from Claude response."""
        actions = []
        # Look for JSON blocks in response
        import re
        json_blocks = re.findall(r'\{[^{}]+\}', response)

        for block in json_blocks:
            try:
                action = json.loads(block)
                if 'action' in action or 'status' in action:
                    actions.append(action)
            except json.JSONDecodeError:
                continue

        return actions

    def _execute_action(self, action: Dict) -> Dict:
        """Execute a single action."""
        action_type = action.get('action', action.get('status'))

        if action_type == 'read':
            result = self.file_reader.read(action['target'])
            self.log('read', f"Read {action['target']}: {result['success']}")
            return result

        elif action_type == 'write':
            result = self.file_writer.write(
                action['target'],
                action.get('content', '')
            )
            self.log('write', f"Wrote {action['target']}: {result['success']}")
            return result

        elif action_type == 'edit':
            result = self.file_writer.edit(
                action['target'],
                action.get('old', ''),
                action.get('new', '')
            )
            self.log('edit', f"Edited {action['target']}: {result['success']}")
            return result

        elif action_type == 'verify':
            index = action.get('index', action.get('criterion', 0))
            self.task.mark_criterion_verified(index, self.agent_id)
            self.log('verify', f"Verified criterion {index}")
            return {'success': True, 'verified': index}

        elif action_type in ('complete', 'blocked'):
            return action

        return {'success': False, 'error': f'Unknown action: {action_type}'}

    def _all_criteria_verified(self) -> bool:
        """Check if all acceptance criteria verified."""
        return self.task.is_complete()

    def _mark_complete(self):
        """Mark task as complete in database."""
        self.db.update_task(self.task_id, {
            'status': 'complete',
            'completed_at': __import__('datetime').datetime.now().isoformat()
        })
        self.log('complete', f'Task completed in {self.iteration} iterations')

    def get_progress(self) -> Dict[str, Any]:
        """Get current execution progress."""
        verified_count = sum(1 for ac in self.task.acceptance_criteria if ac.verified)
        total_count = len(self.task.acceptance_criteria)

        return {
            'task_id': self.task_id,
            'iteration': self.iteration,
            'max_iterations': self.max_iterations,
            'progress': int((verified_count / total_count) * 100) if total_count else 0,
            'criteria_verified': verified_count,
            'criteria_total': total_count,
            'actions_taken': len(self.actions_log),
            'status': self.task.status.value
        }
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] WorkerAgent initializes with task and project root
- [ ] FileReader reads files within allowed scope
- [ ] FileReader rejects files outside scope
- [ ] FileWriter creates files within allowed scope
- [ ] FileWriter creates parent directories
- [ ] FileWriter rejects writes outside scope
- [ ] FileWriter can edit existing files
- [ ] Worker executes action loop
- [ ] Worker parses actions from Claude response
- [ ] Worker verifies acceptance criteria
- [ ] Worker stops at max iterations
- [ ] Worker marks task complete when criteria met
- [ ] Progress tracking returns accurate status
- [ ] Actions are logged to database

## Tests Required

### test_worker.py

```python
import pytest
import os
from agents.worker import WorkerAgent
from agents.tools.file_reader import FileReader
from agents.tools.file_writer import FileWriter
from db import Database

class TestFileReader:
    def test_reads_allowed_file(self, tmp_path):
        """Reads file in allowed path."""
        (tmp_path / 'test.txt').write_text('hello')
        reader = FileReader([str(tmp_path)])
        result = reader.read(str(tmp_path / 'test.txt'))
        assert result['success']
        assert result['content'] == 'hello'

    def test_rejects_outside_scope(self, tmp_path):
        """Rejects file outside allowed path."""
        reader = FileReader([str(tmp_path)])
        result = reader.read('/etc/passwd')
        assert not result['success']
        assert 'not in allowed scope' in result['error']

class TestFileWriter:
    def test_writes_allowed_file(self, tmp_path):
        """Writes file in allowed path."""
        writer = FileWriter([str(tmp_path)])
        result = writer.write(str(tmp_path / 'new.txt'), 'content')
        assert result['success']
        assert (tmp_path / 'new.txt').read_text() == 'content'

    def test_creates_directories(self, tmp_path):
        """Creates parent directories."""
        writer = FileWriter([str(tmp_path)])
        result = writer.write(str(tmp_path / 'a' / 'b' / 'c.txt'), 'deep')
        assert result['success']
        assert (tmp_path / 'a' / 'b' / 'c.txt').exists()

    def test_rejects_outside_scope(self, tmp_path):
        """Rejects write outside allowed path."""
        writer = FileWriter([str(tmp_path)])
        result = writer.write('/tmp/hacker.txt', 'bad')
        assert not result['success']

class TestWorkerAgent:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / 'test.db'))

    @pytest.fixture
    def task_setup(self, db, tmp_path):
        """Setup project with task."""
        db.create_project('proj1', 'Test')
        db.create_component('comp1', 'proj1', 'Component')
        db.create_manager('mgr1', 'proj1', 'comp1')
        task_id = db.create_task(
            component_id='comp1',
            manager_id='mgr1',
            title='Create hello.py',
            description='Create a hello world file'
        )
        return task_id, str(tmp_path)

    # Integration tests would go here with mocked Claude
```

---

*Status: Pending*
*Estimated Complexity: High*
*Dependencies: 3.3 Task Schema*
