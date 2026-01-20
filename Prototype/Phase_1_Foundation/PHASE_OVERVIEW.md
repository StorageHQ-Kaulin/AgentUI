# Phase 1: Foundation

## Overview

Phase 1 establishes the core infrastructure that all subsequent phases depend on. Without a solid foundation, agents cannot persist state, communicate with Claude, or function properly.

## Dependencies

- None (this is the starting phase)

## Sub-Tasks

| Sub-Task | Description | Status |
|----------|-------------|--------|
| 1.1 Database Setup | SQLite schema & CRUD operations | Pending |
| 1.2 Claude API Integration | Base agent class with API calls | Pending |
| 1.3 Interviewer Agent | First working agent with LLM | Pending |

## Phase Exit Criteria

All conditions must be met before proceeding to Phase 2:

- [ ] SQLite database created with all tables from SYSTEM_ARCHITECTURE.md
- [ ] CRUD operations tested and working for all tables
- [ ] Base agent class can make Claude API calls
- [ ] Rate limiting implemented (respects API limits)
- [ ] Interviewer agent successfully analyzes a project description
- [ ] Interview results persist to database
- [ ] Graph.html can render data from database

## Phase Tests

```
Phase_1_Foundation/
├── tests/
│   ├── test_database.py      # All CRUD operations
│   ├── test_claude_api.py    # API calls, rate limiting
│   └── test_interviewer.py   # End-to-end interview
```

### Test Requirements

1. **Database Tests**
   - Create/Read/Update/Delete for each table
   - Foreign key constraints work
   - Concurrent access doesn't corrupt data

2. **API Tests**
   - Successful Claude API call
   - Rate limiting triggers correctly
   - Error handling for API failures

3. **Interviewer Tests**
   - Can analyze simple project description
   - Can analyze complex multi-feature project
   - Results match expected schema
   - Data persists to database

## Data Model Reference (from Graph.html)

The Graph.html file uses these structures that our database must support:

### Node Schema (maps to `components` table)
```json
{
  "id": "string",
  "label": "string",
  "x": "number",
  "y": "number",
  "type": "root|node",
  "agentId": "string|null",
  "status": "active|complete|pending|in_progress|working|idle|blocked",
  "lastEdited": "timestamp",
  "summary": "string",
  "problem": "string",
  "goals": ["string"],
  "scope": ["string"],
  "requirements": ["string"],
  "metrics": [{"req": "string", "value": "string", "status": "pass|fail|pending", "weight": "number"}],
  "risks": ["string"],
  "testCases": [{"name": "string", "status": "pass|fail|pending", "value": "string", "weight": "number"}],
  "inputs": ["string"],
  "outputs": ["string"],
  "files": [{"name": "string", "path": "string", "type": "file|folder"}],
  "subtasks": [{"title": "string", "logic": "string"}]
}
```

### Edge Schema (maps to `edges` table)
```json
{
  "from": "string",
  "to": "string",
  "label": "string",
  "type": "data|api|auth|schema|log"
}
```

### Agent Schema (maps to `agents` table)
```json
{
  "id": "string",
  "name": "string",
  "dept": "string",
  "initials": "string",
  "status": "active|complete|pending|working|idle"
}
```

## Estimated Complexity

| Sub-Task | Complexity | Reason |
|----------|------------|--------|
| 1.1 Database | Medium | Many tables, relationships |
| 1.2 API Integration | Medium | Rate limiting, error handling |
| 1.3 Interviewer | High | Prompt engineering, parsing |

---

*Status: Pending*
*Last Updated: 2026-01-14*
