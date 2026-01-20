# Agent Project Visualization Template

This tool (`Graph_template.html`) allows you to visualize agentic workflows, dependencies, and project status in a sci-fi dashboard interface. It is a standalone HTML file with embedded logic, making it easy to share and modify.

## Quick Start

1. **Open** `Graph_template.html` in any web browser (Chrome, Firefox, Safari).
2. **Interact** with the dashboard:
   - **Click** nodes to view their Details Panel (Success Criteria, Inputs/Outputs, Logs).
   - **Drag** nodes to rearrange the graph.
   - **Drag** the Details Panel to move it out of the way.
   - **Click** the "TASKS" button (bottom right) to view a high-level checklist.

## How to Configure

The entire visualization is driven by a single JSON object called `ProjectData` located at the top of the `<script>` section in the file.

1. Open `Graph_template.html` in a text editor (VS Code, Notepad++, etc.).
2. Locate `const ProjectData = { ... };` (around line ~540).
3. Edit the JSON data to reflect your project structure.

### Data Schema

#### 1. globalTasks
High-level phases of your project displayed in the "TASKS" panel.
```json
{ "text": "Phase 1: Planning", "done": true }
```

#### 2. agents
The workforce available to assign to nodes.
```json
{ 
  "id": "A1", 
  "name": "Coder Agent", 
  "details": "DEV", 
  "initials": "CA", 
  "status": "active" 
}
```

#### 3. nodes
The core logic blocks of your graph.
- **id**: Unique string ID.
- **label**: Display name.
- **type**: 'root' (glowing border) or 'node'.
- **agentId**: Links to an Agent ID.
- **status**: 'active', 'pending', 'complete', 'blocked', 'working'.
- **metrics**: Array of objects `{ req: "KPI Name", value: "Current/Target", status: "pass"|"fail" }`.
- **inputs/outputs**: Strings describing data flow.

#### 4. edges
Connections between nodes.
- **from/to**: Node IDs.
- **type**: 
  - `data` (Green/White, standard flow)
  - `api` (Blue, commands/triggers)
  - `auth` (Red, permissions/security)
  - `schema` (Yellow, structure definitions)

## Interactive Features
- **Scrolling**: The Details Panel is scrollable for long content.
- **Draggable**: Organize your workspace by dragging panels.
- **Live Edit**: You can edit the HTML file and refresh the browser to see changes immediately.
