# 1.2 Claude API Integration

## Objective

Create a base agent class that handles Claude API communication with proper rate limiting, error handling, and response parsing. This becomes the foundation for all agent types.

## Files to Create

```
Visual/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py        # Abstract base class
│   ├── rate_limiter.py      # API rate limiting
│   └── prompts/
│       └── system_base.txt  # Base system prompt
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    BaseAgent                         │
├─────────────────────────────────────────────────────┤
│ + agent_id: str                                      │
│ + agent_type: str                                    │
│ + db: Database                                       │
│ + rate_limiter: RateLimiter                          │
├─────────────────────────────────────────────────────┤
│ + call_claude(prompt, system) -> str                 │
│ + parse_json_response(response) -> dict              │
│ + log(action, message)                               │
│ + get_scoped_context() -> dict                       │
│ # _build_messages(prompt, system) -> list            │
│ # _handle_rate_limit()                               │
└─────────────────────────────────────────────────────┘
              △
              │
    ┌─────────┴─────────┐
    │                   │
Interviewer        Architect
   Agent              Agent
```

## Implementation

### rate_limiter.py

```python
"""
Rate Limiter for Claude API calls.
Implements token bucket algorithm with configurable limits.
"""
import time
import threading
from dataclasses import dataclass
from typing import Optional

@dataclass
class RateLimitConfig:
    requests_per_minute: int = 50
    requests_per_hour: int = 1000
    tokens_per_minute: int = 100000
    cooldown_seconds: float = 60.0

class RateLimiter:
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._minute_calls = []
        self._hour_calls = []
        self._lock = threading.Lock()

    def can_call(self) -> bool:
        """Check if we can make a call without blocking"""
        self._cleanup_old_calls()
        with self._lock:
            return (len(self._minute_calls) < self.config.requests_per_minute and
                    len(self._hour_calls) < self.config.requests_per_hour)

    def wait_if_needed(self) -> float:
        """Block until a call can be made, return wait time"""
        self._cleanup_old_calls()
        wait_time = 0.0

        with self._lock:
            if len(self._minute_calls) >= self.config.requests_per_minute:
                # Wait until oldest minute call expires
                oldest = self._minute_calls[0]
                wait_time = max(0, 60 - (time.time() - oldest))

            if len(self._hour_calls) >= self.config.requests_per_hour:
                oldest = self._hour_calls[0]
                hour_wait = max(0, 3600 - (time.time() - oldest))
                wait_time = max(wait_time, hour_wait)

        if wait_time > 0:
            time.sleep(wait_time)
        return wait_time

    def record_call(self):
        """Record a successful API call"""
        now = time.time()
        with self._lock:
            self._minute_calls.append(now)
            self._hour_calls.append(now)

    def _cleanup_old_calls(self):
        """Remove calls older than their window"""
        now = time.time()
        with self._lock:
            self._minute_calls = [t for t in self._minute_calls if now - t < 60]
            self._hour_calls = [t for t in self._hour_calls if now - t < 3600]

    def get_status(self) -> dict:
        """Get current rate limit status"""
        self._cleanup_old_calls()
        return {
            'minute_calls': len(self._minute_calls),
            'minute_limit': self.config.requests_per_minute,
            'hour_calls': len(self._hour_calls),
            'hour_limit': self.config.requests_per_hour,
            'can_call': self.can_call()
        }
```

### base_agent.py

```python
"""
Base Agent class for all orchestrator agents.
Handles Claude API communication, logging, and scoped context.
"""
import os
import json
import anthropic
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from .rate_limiter import RateLimiter
from db import Database

@dataclass
class AgentConfig:
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.7

class BaseAgent(ABC):
    """Abstract base class for all agents in the orchestrator."""

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        db: Database,
        config: Optional[AgentConfig] = None
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.db = db
        self.config = config or AgentConfig()
        self.rate_limiter = RateLimiter()

        # Initialize Anthropic client
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = anthropic.Anthropic(api_key=api_key)

    def call_claude(
        self,
        prompt: str,
        system: Optional[str] = None,
        expect_json: bool = False
    ) -> str:
        """
        Make a call to Claude API with rate limiting.

        Args:
            prompt: The user prompt to send
            system: Optional system prompt
            expect_json: If True, request JSON output

        Returns:
            Claude's response text
        """
        # Wait for rate limit if needed
        wait_time = self.rate_limiter.wait_if_needed()
        if wait_time > 0:
            self.log('rate_limit', f'Waited {wait_time:.1f}s for rate limit')

        # Build messages
        messages = [{"role": "user", "content": prompt}]

        # Add JSON instruction if needed
        if expect_json:
            json_instruction = "\n\nRespond with valid JSON only. No explanation or markdown."
            if system:
                system += json_instruction
            else:
                system = json_instruction

        try:
            # Make API call
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=system or "",
                messages=messages
            )

            # Record successful call
            self.rate_limiter.record_call()

            # Extract text content
            result = response.content[0].text

            self.log('api_call', f'Claude responded ({len(result)} chars)')
            return result

        except anthropic.RateLimitError as e:
            self.log('error', f'Rate limit error: {e}')
            # Wait and retry once
            import time
            time.sleep(60)
            return self.call_claude(prompt, system, expect_json)

        except anthropic.APIError as e:
            self.log('error', f'API error: {e}')
            raise

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from Claude's response.
        Handles markdown code blocks and extracts JSON.
        """
        text = response.strip()

        # Remove markdown code blocks
        if text.startswith('```'):
            lines = text.split('\n')
            # Remove first and last lines (```json and ```)
            text = '\n'.join(lines[1:-1])

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            self.log('error', f'JSON parse error: {e}')
            # Try to find JSON in response
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Could not parse JSON from response: {text[:200]}...")

    def log(self, action: str, message: str, level: str = 'info'):
        """Log an action to the database."""
        self.db.create_log(
            agent_id=self.agent_id,
            action=action,
            message=message,
            level=level
        )

    @abstractmethod
    def get_scoped_context(self) -> Dict[str, Any]:
        """
        Get the scoped context this agent can see.
        Each agent type defines what it has access to.
        """
        pass

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute the agent's main task."""
        pass

    def get_system_prompt(self) -> str:
        """Load the system prompt for this agent type."""
        prompt_path = os.path.join(
            os.path.dirname(__file__),
            'prompts',
            f'{self.agent_type}.txt'
        )
        if os.path.exists(prompt_path):
            with open(prompt_path, 'r') as f:
                return f.read()
        return ""
```

### prompts/system_base.txt

```
You are an AI agent in an orchestrator system. Your role is defined by your agent type.

CORE PRINCIPLES:
1. Only work with the data you are given (scoped context)
2. Output structured JSON when requested
3. Be concise and actionable
4. Log important decisions

You have access to:
- Your scoped context (provided in each request)
- The ability to suggest next actions
- The database schema for reference

Always respond in the format requested. If JSON is requested, output valid JSON only.
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] `RateLimiter` class implements token bucket algorithm
- [ ] `RateLimiter` correctly limits requests per minute
- [ ] `RateLimiter` correctly limits requests per hour
- [ ] `BaseAgent` can be instantiated with database
- [ ] `BaseAgent.call_claude()` makes successful API call
- [ ] `BaseAgent.call_claude()` respects rate limits
- [ ] `BaseAgent.call_claude()` handles API errors gracefully
- [ ] `BaseAgent.parse_json_response()` extracts JSON from markdown
- [ ] `BaseAgent.parse_json_response()` handles malformed JSON
- [ ] `BaseAgent.log()` writes to database
- [ ] System prompts load correctly
- [ ] ANTHROPIC_API_KEY validation works

## Tests Required

### test_rate_limiter.py

```python
import pytest
import time
from agents.rate_limiter import RateLimiter, RateLimitConfig

class TestRateLimiter:
    def test_allows_initial_calls(self):
        """Fresh limiter allows calls"""
        limiter = RateLimiter()
        assert limiter.can_call() == True

    def test_blocks_after_limit(self):
        """Limiter blocks after minute limit"""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = RateLimiter(config)

        limiter.record_call()
        limiter.record_call()

        assert limiter.can_call() == False

    def test_recovers_after_window(self):
        """Limiter allows calls after window passes"""
        config = RateLimitConfig(requests_per_minute=1)
        limiter = RateLimiter(config)

        limiter.record_call()
        assert limiter.can_call() == False

        # Simulate time passing (hack the internal state)
        limiter._minute_calls = [time.time() - 61]
        limiter._cleanup_old_calls()

        assert limiter.can_call() == True

    def test_status_reporting(self):
        """Status returns accurate counts"""
        limiter = RateLimiter()
        limiter.record_call()

        status = limiter.get_status()
        assert status['minute_calls'] == 1
        assert status['can_call'] == True
```

### test_base_agent.py

```python
import pytest
from unittest.mock import Mock, patch
from agents.base_agent import BaseAgent, AgentConfig
from db import Database

# Concrete implementation for testing
class TestableAgent(BaseAgent):
    def get_scoped_context(self):
        return {'test': True}

    def execute(self):
        return "executed"

class TestBaseAgent:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / 'test.db'))

    @pytest.fixture
    def agent(self, db):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            with patch('anthropic.Anthropic'):
                return TestableAgent('test-agent', 'test', db)

    def test_initialization(self, agent):
        """Agent initializes with correct attributes"""
        assert agent.agent_id == 'test-agent'
        assert agent.agent_type == 'test'

    def test_missing_api_key(self, db):
        """Raises error without API key"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                TestableAgent('test', 'test', db)

    def test_parse_json_simple(self, agent):
        """Parses clean JSON"""
        result = agent.parse_json_response('{"key": "value"}')
        assert result == {'key': 'value'}

    def test_parse_json_markdown(self, agent):
        """Parses JSON from markdown code block"""
        response = '''```json
{"key": "value"}
```'''
        result = agent.parse_json_response(response)
        assert result == {'key': 'value'}

    def test_parse_json_with_text(self, agent):
        """Extracts JSON from mixed text"""
        response = 'Here is the result: {"key": "value"} Hope this helps!'
        result = agent.parse_json_response(response)
        assert result == {'key': 'value'}
```

## Environment Setup

Agents require the following environment variable:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Or in `.env` file:
```
ANTHROPIC_API_KEY=your-api-key-here
```

## Dependencies

Add to requirements.txt:
```
anthropic>=0.39.0
python-dotenv>=1.0.0
```

---

*Status: Pending*
*Estimated Complexity: Medium*
*Dependencies: 1.1 Database Setup*
