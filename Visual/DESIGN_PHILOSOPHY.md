# Agent Dashboard - Design Philosophy

## Core Principle: Compartmentalization

> **An agent should only see the data it needs, nothing more.**

Overloading agents with irrelevant context leads to:
- Slower processing
- Hallucinations and confusion
- Unnecessary token consumption
- Reduced accuracy

---

## Key Design Decisions

### 1. Scoped Data Access
Each component/folder has its **own isolated state**:
```
/CSV_DUMPS/state.json      ← Only CSV input state
/Scrapers/V2/state.json    ← Only V2 scraper state
/enriched_csvs/state.json  ← Only output state
```

Agents query **only their scope**, not the entire system.

### 2. SQLite Over Files
**Why SQLite:**
- Handles concurrent reads/writes safely
- ACID transactions prevent data corruption
- Single file, no server dependencies
- Query specific rows, not entire dataset

**Why NOT flat JSON files:**
- File locks cause race conditions
- Must read entire file even for small updates
- No transactional safety

### 3. Hierarchical State
```
System (global overview)
  └─ Component (folder/module)
       └─ Task (specific work item)
            └─ Log entries
```

Agents operate at the **Task level**. The dashboard aggregates for humans.

### 4. Write-Append, Read-Scoped
- **Writes**: Agents append updates (never overwrite history)
- **Reads**: Dashboard pulls from DB, agents pull only their scope

---

## Anti-Patterns to Avoid

| ❌ Don't | ✅ Do Instead |
|----------|---------------|
| Pass entire system state to an agent | Pass only the component's state |
| Store all data in one mega-JSON | Use SQLite tables with scoped queries |
| Have agents read other agents' logs | Each agent sees only its own scope |
| Real-time sync for everything | Poll or push only changed components |

---

## Summary

**Less context = better agent performance.**

The dashboard shows humans the full picture. Agents see only their slice.
