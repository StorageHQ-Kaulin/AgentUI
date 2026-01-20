# 4.2 Claude Code Integration

## Objective

Integrate with Claude Code CLI for actual code execution. Workers use Claude Code to perform file operations and run commands in a controlled environment.

## Files to Create

```
Visual/
├── agents/
│   └── claude_code_executor.py  # Claude Code CLI wrapper
├── config/
│   └── claude_code.py           # Configuration
```

## Claude Code CLI Interface

Based on ralph-claude-code patterns:

```bash
# Basic execution
claude -p "Your prompt here" --output-format json

# With tool restrictions
claude -p "prompt" --allowed-tools "Write,Read,Bash(git *)"

# Continue session
claude --continue -p "follow up"
```

## Implementation

### config/claude_code.py

```python
"""Configuration for Claude Code integration."""
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ClaudeCodeConfig:
    """Configuration for Claude Code CLI execution."""

    # Output format
    output_format: str = "json"

    # Tool permissions
    allowed_tools: List[str] = None

    # Session management
    use_continue: bool = True
    session_timeout_hours: int = 24

    # Execution limits
    max_iterations: int = 20
    timeout_minutes: int = 30

    # Safety
    require_approval: bool = False
    sandbox_mode: bool = False

    def __post_init__(self):
        if self.allowed_tools is None:
            self.allowed_tools = [
                "Write",
                "Read",
                "Edit",
                "Bash(git *)",
                "Bash(npm *)",
                "Bash(python *)",
                "Bash(pytest *)"
            ]

    def to_cli_args(self) -> List[str]:
        """Convert to CLI arguments."""
        args = []

        args.extend(["--output-format", self.output_format])

        if self.allowed_tools:
            tools_str = ",".join(self.allowed_tools)
            args.extend(["--allowed-tools", tools_str])

        if self.use_continue:
            args.append("--continue")

        return args
```

### claude_code_executor.py

```python
"""
Claude Code CLI Executor - Runs tasks through Claude Code CLI.
"""
import subprocess
import json
import os
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from config.claude_code import ClaudeCodeConfig

@dataclass
class ExecutionResult:
    """Result from Claude Code execution."""
    success: bool
    output: str
    session_id: Optional[str] = None
    files_changed: List[str] = None
    errors: List[str] = None
    duration_seconds: float = 0
    cost_estimate: float = 0

class ClaudeCodeExecutor:
    """Executes prompts through Claude Code CLI."""

    def __init__(self, config: Optional[ClaudeCodeConfig] = None, working_dir: str = "."):
        self.config = config or ClaudeCodeConfig()
        self.working_dir = os.path.abspath(working_dir)
        self.session_id = None
        self.session_file = os.path.join(working_dir, '.claude_session_id')

    def execute(self, prompt: str, timeout: Optional[int] = None) -> ExecutionResult:
        """
        Execute a prompt through Claude Code CLI.

        Args:
            prompt: The prompt to send to Claude Code
            timeout: Timeout in seconds (default from config)

        Returns:
            ExecutionResult with output and metadata
        """
        timeout = timeout or (self.config.timeout_minutes * 60)

        # Build command
        cmd = self._build_command(prompt)

        # Execute
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            duration = time.time() - start_time

            # Parse output
            return self._parse_output(result, duration)

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="",
                errors=["Execution timed out"],
                duration_seconds=timeout
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                errors=[str(e)],
                duration_seconds=time.time() - start_time
            )

    def _build_command(self, prompt: str) -> List[str]:
        """Build Claude Code CLI command."""
        cmd = ["claude"]

        # Add config args
        cmd.extend(self.config.to_cli_args())

        # Add prompt
        cmd.extend(["-p", prompt])

        return cmd

    def _parse_output(self, result: subprocess.CompletedProcess, duration: float) -> ExecutionResult:
        """Parse Claude Code CLI output."""
        output = result.stdout

        # Try to parse as JSON
        try:
            data = json.loads(output)
            return ExecutionResult(
                success=result.returncode == 0,
                output=data.get('result', output),
                session_id=data.get('sessionId'),
                files_changed=data.get('metadata', {}).get('files_changed', []),
                errors=data.get('errors', []) if result.returncode != 0 else None,
                duration_seconds=duration,
                cost_estimate=data.get('metadata', {}).get('cost', 0)
            )
        except json.JSONDecodeError:
            # Plain text output
            return ExecutionResult(
                success=result.returncode == 0,
                output=output,
                errors=[result.stderr] if result.stderr else None,
                duration_seconds=duration
            )

    def execute_task(self, task: 'Task') -> ExecutionResult:
        """
        Execute a full task through Claude Code.

        Args:
            task: Task object with details

        Returns:
            ExecutionResult
        """
        prompt = self._build_task_prompt(task)
        return self.execute(prompt)

    def _build_task_prompt(self, task: 'Task') -> str:
        """Build execution prompt from task."""
        prompt = f"""
# Task: {task.title}

## Description
{task.description}

## Implementation Approach
{task.logic}

## Acceptance Criteria
"""
        for i, ac in enumerate(task.acceptance_criteria, 1):
            prompt += f"{i}. {ac.description}\n"

        prompt += "\n## Files to Create\n"
        for f in task.files_to_create:
            prompt += f"- {f.path}\n"

        prompt += "\n## Files to Modify\n"
        for f in task.files_to_modify:
            prompt += f"- {f.path}\n"

        prompt += """
## Instructions
1. Read any existing files you need to understand
2. Implement the changes according to the description
3. Verify each acceptance criterion is met
4. Report completion when done

Begin implementation.
"""
        return prompt

    def check_available(self) -> bool:
        """Check if Claude Code CLI is available."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False

    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information."""
        return {
            'session_id': self.session_id,
            'working_dir': self.working_dir,
            'config': {
                'output_format': self.config.output_format,
                'allowed_tools': self.config.allowed_tools,
                'use_continue': self.config.use_continue
            }
        }
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] ClaudeCodeConfig stores execution settings
- [ ] Config generates valid CLI arguments
- [ ] Executor builds correct CLI commands
- [ ] Executor handles JSON output format
- [ ] Executor handles text output fallback
- [ ] Executor captures session ID
- [ ] Executor tracks files changed
- [ ] Executor respects timeout
- [ ] Executor handles CLI errors gracefully
- [ ] Task prompts include all required info
- [ ] Session continuity works across calls
- [ ] `check_available()` detects CLI presence

## Tests Required

### test_claude_code_executor.py

```python
import pytest
from unittest.mock import patch, MagicMock
from agents.claude_code_executor import ClaudeCodeExecutor, ExecutionResult
from config.claude_code import ClaudeCodeConfig

class TestClaudeCodeConfig:
    def test_default_tools(self):
        """Default tools are set."""
        config = ClaudeCodeConfig()
        assert "Write" in config.allowed_tools
        assert "Read" in config.allowed_tools

    def test_to_cli_args(self):
        """Generates valid CLI args."""
        config = ClaudeCodeConfig(
            output_format="json",
            allowed_tools=["Write", "Read"],
            use_continue=True
        )
        args = config.to_cli_args()
        assert "--output-format" in args
        assert "json" in args
        assert "--allowed-tools" in args
        assert "--continue" in args

class TestClaudeCodeExecutor:
    @pytest.fixture
    def executor(self, tmp_path):
        return ClaudeCodeExecutor(working_dir=str(tmp_path))

    def test_build_command(self, executor):
        """Builds valid command."""
        cmd = executor._build_command("test prompt")
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "test prompt" in cmd

    def test_parse_json_output(self, executor):
        """Parses JSON output correctly."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"result": "done", "sessionId": "sess123"}'
        mock_result.stderr = ''

        result = executor._parse_output(mock_result, 1.5)

        assert result.success
        assert result.output == "done"
        assert result.session_id == "sess123"

    def test_parse_text_output(self, executor):
        """Falls back to text parsing."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'Plain text output'
        mock_result.stderr = ''

        result = executor._parse_output(mock_result, 1.0)

        assert result.success
        assert result.output == 'Plain text output'

    @patch('subprocess.run')
    def test_execute_success(self, mock_run, executor):
        """Successful execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "completed"}',
            stderr=''
        )

        result = executor.execute("do something")

        assert result.success
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_execute_timeout(self, mock_run, executor):
        """Handles timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

        result = executor.execute("slow task", timeout=30)

        assert not result.success
        assert "timed out" in result.errors[0]
```

---

*Status: Pending*
*Estimated Complexity: High*
*Dependencies: 4.1 Worker Agent Framework*
