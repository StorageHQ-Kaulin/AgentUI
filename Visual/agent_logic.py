"""
================================================================================
                                   GLOSSARY
================================================================================
PURPOSE:
    Implements the 'brain' of the system, acting as the domain logic layer.
    It contains the specific agent classes (Interviewer, Architect) that process
    inputs into structured graph data.

USER INPUTS:
    - user_prompt (String): The raw project description from the user.

OUTPUTS:
    - graph_data (JSON Dictionary): A fully structured object containing nodes, 
      edges, global tasks, and agent definitions ready for the UI.

KEY FUNCTIONS:
    - Interviewer.analyze(user_prompt): 
        Converts raw text -> Structured Project Brief (dict).
    - Architect.design(brief): 
        Converts Project Brief -> Graph Nodes/Edges implementation.
    - generate_graph(user_prompt): 
        Orchestrator function that pipelines the Interviewer and Architect.
================================================================================
"""
import json
import random
import datetime

class Interviewer:
    """
    Role: Analyzes the user's request and creates a structured project brief.
    phases: Interview -> Brief
    """
    def analyze(self, user_prompt):
        print(f"[Interviewer] Analyzing: {user_prompt}")
        
        # Simple heuristic analysis (simulating an LLM)
        brief = {
            "title": "New Project",
            "goal": user_prompt,
            "core_components": [],
            "requirements": [],
            "risks": []
        }

        prompt_lower = user_prompt.lower()

        # Heuristic 1: Detect specific types of projects
        if "scraper" in prompt_lower or "crawl" in prompt_lower:
            brief["title"] = "Web Scraper Project"
            brief["core_components"].extend(["Target Website", "Scraper Engine", "Data Parser", "CSV Output"])
            brief["requirements"].append("Handle anti-bot protections")
            brief["risks"].append("IP blocking")
        
        elif "dashboard" in prompt_lower or "ui" in prompt_lower:
            brief["title"] = "Dashboard Visualization"
            brief["core_components"].extend(["Frontend UI", "API Layer", "Data Store"])
            brief["requirements"].append("Responsive design")
        
        elif "api" in prompt_lower or "backend" in prompt_lower:
            brief["title"] = "Backend API Service"
            brief["core_components"].extend(["API Router", "Auth Middleware", "Database"])
        
        else:
            brief["title"] = "Custom Automation"
            brief["core_components"].extend(["Input Handler", "Processing Unit", "Output Generator"])

        print(f"[Interviewer] Brief created: {brief['title']}")
        return brief

class Architect:
    """
    Role: Takes the project brief and designs the system architecture (Nodes & Edges).
    phases: Brief -> Graph
    """
    def design(self, brief):
        print(f"[Architect] Designing system for: {brief['title']}")
        
        nodes = []
        edges = []
        
        # 1. Root Node (The Goal)
        root_id = "ROOT"
        nodes.append({
            "id": root_id,
            "label": brief["title"],
            "x": 500, "y": 50,
            "type": "root",
            "agentId": None,
            "status": "active",
            "summary": brief["goal"],
            "inputs": ["User Request"],
            "outputs": ["Completed System"],
            "metrics": [{"req": "Completion", "value": "0%", "status": "pending"}],
            "risks": brief["risks"],
            "files": []
        })


        # 2. Component Nodes
        x_pos = 500
        y_start = 200
        y_spacing = 150
        
        previous_node_id = root_id
        
        for i, comp_name in enumerate(brief["core_components"]):
            node_id = f"NODE_{i}"
            nodes.append({
                "id": node_id,
                "label": comp_name,
                "x": x_pos,
                "y": y_start + (i * y_spacing),
                "type": "node",
                "agentId": f"A{i+1}",
                "status": "pending",
                "summary": f"Implementation of {comp_name}",
                "inputs": [f"Input for {comp_name}"],
                "outputs": [f"Output of {comp_name}"],
                "metrics": [{"req": "Unit Tests", "value": "Pending", "status": "pending"}],
                "subtasks": [{"title": "Setup", "logic": "Init framework"}, {"title": "Develop", "logic": "Write code"}],
                "files": []
            })
            
            # Connect to previous node or root
            if i == 0:
                edges.append({"from": root_id, "to": node_id, "label": "Initiates", "type": "data"})
            else:
                edges.append({"from": previous_node_id, "to": node_id, "label": "Flows By", "type": "data"})
            
            previous_node_id = node_id

        # 3. Agents (One per component for now)
        agents = []
        for i, comp_name in enumerate(brief["core_components"]):
            agents.append({
                "id": f"A{i+1}",
                "name": f"{comp_name} Specialist",
                "dept": "DEV",
                "initials": comp_name[:2].upper(),
                "status": "idle"
            })

        # 4. Global Tasks
        global_tasks = [
            {"text": "Phase 1: Interview & Design", "done": True},
            {"text": "Phase 2: Component Implementation", "done": False},
            {"text": "Phase 3: Integration Testing", "done": False}
        ]

        # Final Graph Data
        graph_data = {
            "projectName": brief["title"],
            "projectSummary": brief["goal"],
            "globalTasks": global_tasks,
            "agents": agents,
            "nodes": nodes,
            "edges": edges,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        return graph_data

def generate_graph(user_prompt):
    interviewer = Interviewer()
    architect = Architect()
    
    brief = interviewer.analyze(user_prompt)
    graph_data = architect.design(brief)
    
    return graph_data

if __name__ == "__main__":
    # Test run
    test_prompt = "I want to build a python scraper for scraping generic news sites"
    result = generate_graph(test_prompt)
    print(json.dumps(result, indent=2))
