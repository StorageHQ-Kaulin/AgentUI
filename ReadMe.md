# Agent Orchestrator

A multi-agent system for orchestrating AI agents through a 7-phase software development pipeline. The system uses Claude Code CLI for LLM-powered analysis and provides a visual interface for project planning and component management.

## Features

- **Interview Phase**: AI-powered project discovery that decomposes project ideas into well-defined components
- **Visual Architecture**: Interactive Mermaid diagrams showing component relationships
- **Component Management**: Detailed view of each component with goals, requirements, risks, and test cases
- **Clarifying Questions**: Iterative refinement through AI-generated questions
- **Persistent Storage**: SQLite database for project and component data

## Getting Started

### Prerequisites

- Python 3.10+
- [Claude Code CLI](https://github.com/anthropics/claude-code) installed and authenticated

### Running the Server

```bash
cd Visual
python server.py
```

The server will start at http://localhost:3842

### Usage

1. Open http://localhost:3842/Interview.html
2. Describe your project idea
3. Review the generated components and architecture
4. Answer clarifying questions to refine the analysis
5. Click on components to view and edit details

## Project Structure

```
Agent_Orchestrator/
├── Visual/
│   ├── server.py          # Main HTTP server
│   ├── Interview.html     # Interview UI
│   ├── Graph.html         # Graph visualization
│   ├── agents/            # LLM-powered agents
│   │   ├── base_agent.py  # Base agent class
│   │   ├── interviewer.py # Project interviewer
│   │   └── prompts/       # Agent system prompts
│   ├── db/                # Database layer
│   │   ├── database.py    # SQLite operations
│   │   └── models.py      # Data models
│   └── api/               # API helpers
└── Prototype/             # Earlier prototype versions
```

## Known Issues

- **Live Architecture Generation Bug**: The Mermaid diagram may occasionally fail to render with errors like "translate(undefined, NaN)" or "Could not find a suitable point". This happens when edge references point to nodes that don't exist after ID sanitization. Refreshing the page or loading a saved project usually resolves this.

## Tech Stack

- **Backend**: Python with built-in http.server
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **LLM**: Claude via Claude Code CLI
- **Database**: SQLite
- **Diagrams**: Mermaid.js

## License

MIT
