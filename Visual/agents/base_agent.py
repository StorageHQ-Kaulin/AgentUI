"""
Base Agent class for all orchestrator agents.
Uses Claude Code CLI for all LLM calls.
"""
import os
import json
import re
import time
import subprocess
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from .rate_limiter import RateLimiter
import sys
# Add parent directory to path for db import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from db import Database
except ImportError:
    # Fallback if running from root
    from Visual.db import Database


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""
    model: str = "claude-opus-4-5-20251101"  # Most advanced model for high-quality analysis
    max_tokens: int = 4096
    temperature: float = 0.7

# Model options for different use cases (Claude 4.5)
MODELS = {
    "fast": "claude-haiku-4-5-20251001",      # Fastest
    "balanced": "claude-sonnet-4-5-20250929", # Smart for complex tasks
    "powerful": "claude-opus-4-5-20251101"    # Maximum intelligence
}


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the orchestrator.

    Provides:
    - Claude Code CLI integration with rate limiting
    - JSON response parsing
    - Logging to database
    - Scoped context management
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        db: Database,
        config: Optional[AgentConfig] = None
    ):
        """
        Initialize the base agent.

        Args:
            agent_id: Unique identifier for this agent instance
            agent_type: Type of agent (e.g., 'interviewer', 'architect')
            db: Database instance for persistence
            config: Optional agent configuration
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.db = db
        self.config = config or AgentConfig()
        self.rate_limiter = RateLimiter()

    def call_claude(
        self,
        prompt: str,
        system: Optional[str] = None,
        expect_json: bool = False,
        max_retries: int = 3
    ) -> str:
        """
        Make a call to Claude via the CLI with rate limiting and error handling.

        Args:
            prompt: The user prompt to send
            system: Optional system prompt
            expect_json: If True, request JSON output
            max_retries: Number of retries on errors

        Returns:
            Claude's response text

        Raises:
            RuntimeError: If CLI execution fails
        """
        # Add JSON instruction if needed
        if expect_json:
            json_instruction = (
                "\n\nIMPORTANT: Respond with valid JSON only. "
                "No explanation, no markdown code blocks, just raw JSON."
            )
            if system:
                system += json_instruction
            else:
                system = json_instruction

        return self._call_cli(prompt, system, max_retries)

    def _call_cli(self, prompt: str, system: Optional[str], max_retries: int = 3) -> str:
        """
        Execute call using local 'claude' CLI (Claude Code).
        """
        full_prompt = prompt
        if system:
            full_prompt = f"System: {system}\n\nUser: {prompt}"

        # Wait for rate limit if needed
        wait_time = self.rate_limiter.wait_if_needed()
        if wait_time > 0:
            self.log('rate_limit', f'Waited {wait_time:.1f}s for rate limit')
            time.sleep(wait_time)

        start = time.time()
        model_display = self.config.model.split('-')[1] if '-' in self.config.model else self.config.model
        print(f"[Claude Code] {model_display}...", end="", flush=True)

        for attempt in range(max_retries):
            try:
                # Build command
                cmd = ['claude', '-p', full_prompt, '--dangerously-skip-permissions']

                # Add model flag if specified
                if self.config.model:
                    cmd.extend(['--model', self.config.model])

                # Create env copy without API key to force local auth
                cli_env = os.environ.copy()
                if 'ANTHROPIC_API_KEY' in cli_env:
                    del cli_env['ANTHROPIC_API_KEY']

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    env=cli_env,
                    timeout=180  # 3 minute timeout
                )

                output = result.stdout
                elapsed = time.time() - start

                self.rate_limiter.record_call()
                print(f" done ({elapsed:.1f}s)")
                self.log('cli_call', f'Responded in {elapsed:.1f}s ({len(output)} chars)')

                return output

            except subprocess.TimeoutExpired:
                self.log('error', f'CLI timed out (attempt {attempt + 1})')
                if attempt < max_retries - 1:
                    print(f" timeout, retry {attempt + 2}...", end="", flush=True)
                    time.sleep(2)
                else:
                    print(" timed out")
                    raise RuntimeError("Claude Code CLI timed out after 3 minutes")
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr[:500] if e.stderr else str(e)
                self.log('error', f'CLI execution failed (attempt {attempt + 1}): {error_msg}')
                print(f"\n[Error] {error_msg[:200]}")
                if attempt < max_retries - 1:
                    print(f" retry {attempt + 2}...", end="", flush=True)
                    time.sleep(2)  # Brief pause before retry
                else:
                    print(" failed")
                    raise RuntimeError(f"Claude Code CLI failed: {error_msg}")
            except FileNotFoundError:
                self.log('error', 'claude executable not found in PATH')
                print(" not found")
                raise RuntimeError(
                    "Claude Code CLI not found. "
                    "Install it from: https://github.com/anthropics/claude-code"
                )

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from Claude's response.

        Handles markdown code blocks and extracts JSON from mixed text.

        Args:
            response: The raw response text from Claude

        Returns:
            Parsed JSON as a dictionary

        Raises:
            ValueError: If JSON cannot be parsed
        """
        text = response.strip()

        # Remove markdown code blocks
        if text.startswith('```'):
            lines = text.split('\n')
            # Find the end of the code block
            end_idx = len(lines) - 1
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip() == '```':
                    end_idx = i
                    break
            # Remove first line (```json) and last line (```)
            text = '\n'.join(lines[1:end_idx])

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in response
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Try to find JSON array in response
        array_match = re.search(r'\[[\s\S]*\]', text)
        if array_match:
            try:
                return json.loads(array_match.group())
            except json.JSONDecodeError:
                pass

        self.log('error', f'JSON parse error. Response: {text[:200]}...')
        raise ValueError(f"Could not parse JSON from response: {text[:200]}...")

    def log(self, action: str, message: str, level: str = 'info'):
        """
        Log an action to the database.

        Args:
            action: The action being logged (e.g., 'cli_call', 'error')
            message: Description of the action
            level: Log level ('debug', 'info', 'warn', 'error')
        """
        try:
            self.db.create_log(
                agent_id=self.agent_id,
                action=action,
                message=message,
                level=level
            )
        except Exception as e:
            # Don't let logging failures break the agent
            print(f"[{self.agent_type}:{self.agent_id}] {level.upper()}: {action} - {message}")
            print(f"  (Failed to write to DB: {e})")

    @abstractmethod
    def get_scoped_context(self) -> Dict[str, Any]:
        """
        Get the scoped context this agent can see.

        Each agent type defines what it has access to.
        This prevents agents from accessing data outside their scope.

        Returns:
            Dictionary describing the agent's context and restrictions.
        """
        pass

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the agent's main task.

        Implementation varies by agent type.
        """
        pass

    def get_system_prompt(self) -> str:
        """
        Load the system prompt for this agent type.

        Returns:
            The system prompt string, or empty string if not found.
        """
        prompt_path = os.path.join(
            os.path.dirname(__file__),
            'prompts',
            f'{self.agent_type}.txt'
        )
        if os.path.exists(prompt_path):
            with open(prompt_path, 'r') as f:
                return f.read()
        return ""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.agent_id} type={self.agent_type}>"
