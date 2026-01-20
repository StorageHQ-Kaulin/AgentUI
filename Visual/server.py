"""
================================================================================
                                   GLOSSARY
================================================================================
PURPOSE:
    Local HTTP server acting as the communication bridge between the Frontend UI
    and the Python backend logic.

USER INPUTS:
    - POST /api/start_interview:
        Expects JSON body { "prompt": "..." }
    - GET /api/graph_data:
        Expects no parameters.
    - GET /api/projects:
        List all projects from database.
    - GET /api/project/<id>:
        Get a specific project's graph data.
    - GET /open?path=...:
        Expects a file path query parameter.

OUTPUTS:
    - JSON responses with success/error status and data payloads.
    - Writes generated graph data to 'graph_data.json' on disk (legacy support).
    - Persists data to SQLite database.

KEY FUNCTIONS:
    - do_POST():
        Handles 'start_interview', triggers agent logic, saves result to disk/DB.
    - do_GET():
        Serves static HTML/JS files and handles data fetch endpoints.
================================================================================
"""

import http.server
import socketserver
import subprocess
import urllib.parse
import os
import json
import sys
import traceback

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print("[Server] Loaded .env file")
except ImportError:
    print("[Server] python-dotenv not installed, using system environment only")

# Try to import new agent system, fall back to legacy
USE_NEW_AGENTS = False
import shutil

# Check if Claude Code CLI is available
CLAUDE_CLI_AVAILABLE = shutil.which('claude') is not None

try:
    from db import Database
    from agents import InterviewerAgent, ArchitectAgent
    from api import APIHandler
    from analyzers import CodebaseScanner

    if CLAUDE_CLI_AVAILABLE:
        USE_NEW_AGENTS = True
        print(f"[Server] Using Claude Code CLI for LLM calls")
    else:
        print("[Server] Claude Code CLI not found in PATH")
        print("[Server] Install from: https://github.com/anthropics/claude-code")
        print("[Server] Falling back to legacy heuristic agents")
except ImportError as e:
    print(f"[Server] Could not import new agents: {e}")
    print("[Server] Falling back to legacy agent_logic")

# Import legacy agent logic as fallback
import agent_logic

PORT = 3842
# We run this from dashboard/Visual, but the project root is 2 levels up
PROJECT_ROOT = os.path.abspath(os.path.join(os.getcwd(), "../../"))

print(f"Project Root determined as: {PROJECT_ROOT}")

# Initialize database and API handler if using new agents
db = None
api = None
if USE_NEW_AGENTS:
    try:
        db = Database()
        api = APIHandler(db)
        print(f"[Server] Database initialized at: {db.db_path}")
    except Exception as e:
        print(f"[Server] Database initialization failed: {e}")
        traceback.print_exc()
        USE_NEW_AGENTS = False


class AgenticHandler(http.server.SimpleHTTPRequestHandler):

    def do_POST(self):
        """Handle API POST calls."""
        parsed_path = urllib.parse.urlparse(self.path)

        if parsed_path.path == '/api/start_interview':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                user_prompt = data.get('prompt')
                model = data.get('model')  # Optional model override

                if not user_prompt:
                    self.send_json({'status': 'error', 'message': 'No prompt provided'}, 400)
                    return

                print(f"[Server] Received prompt: {user_prompt[:100]}...")
                if model:
                    print(f"[Server] Using model: {model}")

                # Use new agents if available, otherwise fall back to legacy
                if USE_NEW_AGENTS and db:
                    graph_data, brief = self._run_new_interview(user_prompt, model=model)
                    # Store brief in memory for refinement
                    self._current_brief = brief
                else:
                    graph_data = agent_logic.generate_graph(user_prompt)
                    self._current_brief = None

                # Save to graph_data.json (legacy support for Graph.html)
                output_path = os.path.join(os.getcwd(), 'graph_data.json')
                with open(output_path, 'w') as f:
                    json.dump(graph_data, f, indent=2)

                print(f"[Server] Graph data saved to {output_path}")
                self.send_json({'status': 'success', 'data': graph_data})

            except Exception as e:
                print(f"[Server] Error processing interview: {e}")
                traceback.print_exc()
                self.send_json({'status': 'error', 'message': str(e)}, 500)
            return

        # Refine interview with answers to clarifying questions
        if parsed_path.path == '/api/refine_interview':
            if not USE_NEW_AGENTS or not db:
                self.send_json({'status': 'error', 'message': 'LLM agents not available'}, 503)
                return

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                original_brief = data.get('brief')
                answers = data.get('answers', {})
                additional_context = data.get('additional_context', '')
                model = data.get('model')  # Optional model override

                if not original_brief:
                    self.send_json({'status': 'error', 'message': 'No brief provided'}, 400)
                    return

                print(f"[Server] Refining brief with {len(answers)} answers...")
                if model:
                    print(f"[Server] Using model: {model}")

                graph_data, refined_brief = self._refine_interview(original_brief, answers, additional_context, model=model)
                self._current_brief = refined_brief

                # Save to graph_data.json
                output_path = os.path.join(os.getcwd(), 'graph_data.json')
                with open(output_path, 'w') as f:
                    json.dump(graph_data, f, indent=2)

                print(f"[Server] Refined graph data saved")
                self.send_json({'status': 'success', 'data': graph_data})

            except Exception as e:
                print(f"[Server] Error refining interview: {e}")
                traceback.print_exc()
                self.send_json({'status': 'error', 'message': str(e)}, 500)
            return

        # Generate architecture for a project
        if parsed_path.path.startswith('/api/projects/') and parsed_path.path.endswith('/architecture'):
            if not USE_NEW_AGENTS or not api:
                self.send_json({'status': 'error', 'message': 'LLM agents not available'}, 503)
                return

            # Extract project_id from path: /api/projects/{id}/architecture
            parts = parsed_path.path.split('/')
            project_id = parts[3] if len(parts) >= 4 else None

            if not project_id:
                self.send_json({'status': 'error', 'message': 'Project ID required'}, 400)
                return

            content_length = int(self.headers.get('Content-Length', 0))
            codebase_path = None
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                try:
                    data = json.loads(post_data.decode('utf-8'))
                    codebase_path = data.get('codebase_path')
                except:
                    pass

            print(f"[Server] Generating architecture for project {project_id}...")
            result = api.generate_architecture(project_id, codebase_path)
            self.send_json(result)
            return

        # Analyze a codebase
        if parsed_path.path == '/api/analyze':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                path = data.get('path')

                if not path:
                    self.send_json({'status': 'error', 'message': 'Path required'}, 400)
                    return

                print(f"[Server] Analyzing codebase at {path}...")
                result = api.analyze_codebase(path)
                self.send_json(result)

            except Exception as e:
                print(f"[Server] Error analyzing codebase: {e}")
                traceback.print_exc()
                self.send_json({'status': 'error', 'message': str(e)}, 500)
            return

        # Component Chat - Conversational interface with change capabilities
        if parsed_path.path == '/api/component/chat':
            if not USE_NEW_AGENTS or not db:
                self.send_json({'status': 'error', 'message': 'AI not available'}, 503)
                return

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                component = data.get('component', {})
                message = data.get('message', '')
                history = data.get('history', [])
                project_context = data.get('projectContext', '')
                model = data.get('model')

                print(f"[Server] Component chat: {message[:50]}...")

                result = self._component_chat(component, message, history, project_context, model)
                self.send_json({'status': 'success', 'data': result})

            except Exception as e:
                print(f"[Server] Component chat error: {e}")
                traceback.print_exc()
                self.send_json({'status': 'error', 'message': str(e)}, 500)
            return

        # Component AI interaction - suggestions, questions, expansions (legacy)
        if parsed_path.path == '/api/component/assist':
            if not USE_NEW_AGENTS or not db:
                self.send_json({'status': 'error', 'message': 'AI not available'}, 503)
                return

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                component = data.get('component', {})
                action = data.get('action', 'suggest')  # suggest, expand, question
                user_input = data.get('input', '')
                context = data.get('context', '')
                model = data.get('model')

                print(f"[Server] Component AI assist: {action}")

                result = self._component_ai_assist(component, action, user_input, context, model)
                self.send_json({'status': 'success', 'data': result})

            except Exception as e:
                print(f"[Server] Component assist error: {e}")
                traceback.print_exc()
                self.send_json({'status': 'error', 'message': str(e)}, 500)
            return

        # Approve design and advance phase
        if parsed_path.path.startswith('/api/projects/') and parsed_path.path.endswith('/approve'):
            if not USE_NEW_AGENTS or not api:
                self.send_json({'status': 'error', 'message': 'Database not available'}, 503)
                return

            parts = parsed_path.path.split('/')
            project_id = parts[3] if len(parts) >= 4 else None

            if not project_id:
                self.send_json({'status': 'error', 'message': 'Project ID required'}, 400)
                return

            print(f"[Server] Approving design for project {project_id}...")
            result = api.approve_design(project_id)
            self.send_json(result)
            return

        self.send_error(404, "Endpoint not found")

    def _run_new_interview(self, user_prompt: str, model: str = None) -> tuple:
        """Run interview using new LLM-powered agents."""
        interviewer = InterviewerAgent(db, model=model)
        brief = interviewer.execute(user_prompt)
        graph_data = interviewer.to_graph_data(brief)

        # Add project_id and brief to response for frontend reference
        graph_data['project_id'] = brief.get('project_id')
        graph_data['brief'] = brief  # Include full brief for refinement

        return graph_data, brief

    def _refine_interview(self, original_brief: dict, answers: dict, additional_context: str, model: str = None) -> tuple:
        """Refine interview based on user answers."""
        interviewer = InterviewerAgent(db, model=model)
        refined_brief = interviewer.refine(original_brief, answers, additional_context)
        graph_data = interviewer.to_graph_data(refined_brief)

        graph_data['project_id'] = refined_brief.get('project_id')
        graph_data['brief'] = refined_brief

        return graph_data, refined_brief

    def _component_chat(self, component: dict, message: str, history: list, project_context: str, model: str = None) -> dict:
        """Conversational chat interface for component refinement."""
        from agents.base_agent import AgentConfig
        import subprocess

        config = AgentConfig(model=model) if model else AgentConfig()

        # Build component context
        comp_info = f"""
COMPONENT: {component.get('label', 'Unknown')}
TYPE: {component.get('type', 'node')}
STATUS: {component.get('status', 'pending')}

SUMMARY: {component.get('summary', 'No summary yet')}

PROBLEM: {component.get('problem', 'Not defined')}

GOALS: {json.dumps(component.get('goals', []))}

SCOPE: {json.dumps(component.get('scope', []))}

REQUIREMENTS: {json.dumps(component.get('requirements', []))}

RISKS: {json.dumps(component.get('risks', []))}

TEST CASES: {json.dumps([tc.get('name', tc) if isinstance(tc, dict) else tc for tc in component.get('testCases', [])])}

INPUTS: {json.dumps(component.get('inputs', []))}
OUTPUTS: {json.dumps(component.get('outputs', []))}
"""

        # Build conversation history
        history_text = ""
        for h in history[-6:]:  # Last 6 messages
            role = "User" if h.get('type') == 'user' else "Assistant"
            history_text += f"{role}: {h.get('content', '')}\n"

        prompt = f"""You are a helpful technical architect assistant having a conversation about a software component.

PROJECT CONTEXT: {project_context}

{comp_info}

CONVERSATION HISTORY:
{history_text}

USER'S MESSAGE: {message}

INSTRUCTIONS:
1. Respond conversationally and helpfully to the user's message
2. If they ask for explanations, provide clear, detailed answers
3. If they ask to add/modify requirements, risks, tests, or other fields, include a "changes" object
4. Always be specific and actionable

RESPONSE FORMAT (JSON):
{{
    "response": "Your conversational response to the user (can include HTML like <strong>, <em>, <ul>, <li> for formatting)",
    "changes": {{
        "add_requirements": ["new requirement 1"],
        "add_risks": ["new risk 1"],
        "add_tests": [{{"name": "test description", "type": "unit|integration|e2e", "priority": "high|medium|low"}}],
        "add_goals": ["new goal"],
        "add_scope": ["what is included", "NOT: what is excluded"],
        "add_inputs": ["new input"],
        "add_outputs": ["new output"],
        "summary": "updated summary if requested",
        "problem": "updated problem statement if requested",
        "status": "new status if requested"
    }}
}}

IMPORTANT:
- Only include fields in "changes" if the user asked you to make changes
- If only answering a question, "changes" should be {{}} or omitted
- Be conversational but professional
- Use HTML formatting in responses for readability

Return ONLY valid JSON."""

        try:
            full_prompt = f"System: You are a helpful technical assistant. Always respond with valid JSON only.\n\nUser: {prompt}"
            cmd = ['claude', '-p', full_prompt, '--dangerously-skip-permissions']
            if config.model:
                cmd.extend(['--model', config.model])

            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=90)
            response = result.stdout.strip()

            # Parse JSON from response
            import re
            try:
                return json.loads(response)
            except:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())

            return {"response": response, "changes": {}}

        except subprocess.TimeoutExpired:
            return {"response": "Sorry, the request timed out. Please try again.", "error": "timeout"}
        except subprocess.CalledProcessError as e:
            return {"response": f"Sorry, I encountered an error: {e.stderr[:200]}", "error": str(e)}
        except Exception as e:
            return {"response": f"An error occurred: {str(e)}", "error": str(e)}

    def _component_ai_assist(self, component: dict, action: str, user_input: str, context: str, model: str = None) -> dict:
        """Provide AI assistance for a specific component."""
        from agents.base_agent import AgentConfig
        import subprocess

        config = AgentConfig(model=model) if model else AgentConfig()

        # Build the prompt based on action
        comp_summary = f"""
Component: {component.get('label', 'Unknown')}
Summary: {component.get('summary', 'N/A')}
Problem: {component.get('problem', 'N/A')}
Goals: {', '.join(component.get('goals', []))}
Requirements: {', '.join(component.get('requirements', []))}
Risks: {', '.join(component.get('risks', []))}
Inputs: {', '.join(component.get('inputs', []))}
Outputs: {', '.join(component.get('outputs', []))}
Test Cases: {', '.join([tc.get('name', '') if isinstance(tc, dict) else tc for tc in component.get('testCases', [])])}
"""

        if action == 'suggest':
            prompt = f"""You are a technical architect assistant. Analyze this component and suggest improvements.

{comp_summary}

{f"User's request: {user_input}" if user_input else ""}
{f"Additional context: {context}" if context else ""}

Provide specific, actionable suggestions. Return JSON:
{{
    "suggestions": ["suggestion 1", "suggestion 2"],
    "missing_requirements": ["requirement that should be added"],
    "missing_tests": [{{"name": "test description", "type": "unit|integration|e2e", "priority": "high|medium|low"}}],
    "potential_risks": ["risk to consider"],
    "questions": ["clarifying question if needed"]
}}

Return ONLY valid JSON."""

        elif action == 'expand':
            # When user adds something, expand on it
            prompt = f"""You are a technical architect assistant. The user just added something to this component.

{comp_summary}

User just added: {user_input}
{f"Context: {context}" if context else ""}

Based on this addition, suggest related items that should also be considered. Return JSON:
{{
    "related_requirements": ["related requirement"],
    "related_tests": [{{"name": "test for the new item", "type": "unit", "priority": "medium"}}],
    "related_risks": ["risk introduced by this addition"],
    "explanation": "Brief explanation of why these are related"
}}

Return ONLY valid JSON."""

        elif action == 'question':
            # Answer a question about the component
            prompt = f"""You are a technical architect assistant. Answer the user's question about this component.

{comp_summary}

User's question: {user_input}
{f"Context: {context}" if context else ""}

Provide a helpful, specific answer. Return JSON:
{{
    "answer": "Your detailed answer here",
    "suggestions": ["optional follow-up suggestion"],
    "code_example": "optional code snippet if relevant"
}}

Return ONLY valid JSON."""

        else:
            return {"error": f"Unknown action: {action}"}

        # Call Claude
        try:
            full_prompt = f"System: You are a helpful technical assistant. Always respond with valid JSON only.\n\nUser: {prompt}"
            cmd = ['claude', '-p', full_prompt, '--dangerously-skip-permissions']
            if config.model:
                cmd.extend(['--model', config.model])

            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
            response = result.stdout.strip()

            # Parse JSON from response
            import re
            # Try direct parse
            try:
                return json.loads(response)
            except:
                # Try to extract JSON
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())

            return {"answer": response, "raw": True}

        except subprocess.TimeoutExpired:
            return {"error": "Request timed out"}
        except subprocess.CalledProcessError as e:
            return {"error": f"AI call failed: {e.stderr}"}
        except Exception as e:
            return {"error": str(e)}

    def do_GET(self):
        """Handle API GET calls."""
        parsed_path = urllib.parse.urlparse(self.path)

        # Get graph data (legacy endpoint)
        if parsed_path.path == '/api/graph_data':
            data_path = os.path.join(os.getcwd(), 'graph_data.json')
            if os.path.exists(data_path):
                try:
                    with open(data_path, 'r') as f:
                        data = json.load(f)
                    self.send_json(data)
                except Exception as e:
                    self.send_json({'status': 'error', 'message': str(e)}, 500)
            else:
                self.send_json({'status': 'error', 'message': 'No graph data found. Run interview first.'}, 404)
            return

        # List all projects
        if parsed_path.path == '/api/projects':
            if USE_NEW_AGENTS and db:
                try:
                    projects = db.get_all_projects()
                    self.send_json({
                        'status': 'success',
                        'projects': [p.to_dict() for p in projects]
                    })
                except Exception as e:
                    self.send_json({'status': 'error', 'message': str(e)}, 500)
            else:
                self.send_json({'status': 'error', 'message': 'Database not available'}, 503)
            return

        # Get specific project graph data (legacy endpoint)
        if parsed_path.path.startswith('/api/project/') and not '/graph' in parsed_path.path:
            project_id = parsed_path.path.split('/')[-1]
            if USE_NEW_AGENTS and db:
                try:
                    graph_data = db.get_graph_data(project_id)
                    if graph_data:
                        self.send_json({'status': 'success', 'data': graph_data})
                    else:
                        self.send_json({'status': 'error', 'message': 'Project not found'}, 404)
                except Exception as e:
                    self.send_json({'status': 'error', 'message': str(e)}, 500)
            else:
                self.send_json({'status': 'error', 'message': 'Database not available'}, 503)
            return

        # New API: Get project graph data (Phase 2)
        if parsed_path.path.startswith('/api/projects/') and parsed_path.path.endswith('/graph'):
            parts = parsed_path.path.split('/')
            project_id = parts[3] if len(parts) >= 4 else None
            if USE_NEW_AGENTS and api:
                try:
                    graph_data = api.get_project_graph(project_id)
                    if graph_data:
                        self.send_json(graph_data)
                    else:
                        self.send_json({'status': 'error', 'message': 'Project not found'}, 404)
                except Exception as e:
                    self.send_json({'status': 'error', 'message': str(e)}, 500)
            else:
                self.send_json({'status': 'error', 'message': 'Database not available'}, 503)
            return

        # Get component details
        if parsed_path.path.startswith('/api/components/'):
            component_id = parsed_path.path.split('/')[-1]
            if USE_NEW_AGENTS and api:
                try:
                    comp_data = api.get_component(component_id)
                    if comp_data:
                        self.send_json(comp_data)
                    else:
                        self.send_json({'status': 'error', 'message': 'Component not found'}, 404)
                except Exception as e:
                    self.send_json({'status': 'error', 'message': str(e)}, 500)
            else:
                self.send_json({'status': 'error', 'message': 'Database not available'}, 503)
            return

        # Get all agents
        if parsed_path.path == '/api/agents':
            if USE_NEW_AGENTS and api:
                try:
                    self.send_json(api.get_agents())
                except Exception as e:
                    self.send_json({'status': 'error', 'message': str(e)}, 500)
            else:
                self.send_json({'status': 'error', 'message': 'Database not available'}, 503)
            return

        # Open file in default editor
        if parsed_path.path == '/open':
            query = urllib.parse.parse_qs(parsed_path.query)
            file_path = query.get('path', [None])[0]

            if file_path:
                # Check if it is already absolute
                if file_path.startswith('/'):
                    full_path = file_path
                else:
                    full_path = os.path.join(PROJECT_ROOT, file_path)

                print(f"[Server] Request to open: {full_path}")

                if os.path.exists(full_path):
                    try:
                        # Use 'open' command on Mac which opens in default app
                        subprocess.run(['open', full_path])
                        self.send_json({'status': 'success', 'message': f'Opened {full_path}'})
                    except Exception as e:
                        print(f"[Server] Error executing open: {e}")
                        self.send_json({'status': 'error', 'message': str(e)}, 500)
                else:
                    print(f"[Server] File not found: {full_path}")
                    self.send_json({'status': 'error', 'message': 'File not found'}, 404)
            else:
                self.send_json({'status': 'error', 'message': 'No path provided'}, 400)
            return

        # API status endpoint
        if parsed_path.path == '/api/status':
            # Get model from config
            model_name = "claude-haiku-4-5-20251001"  # Default
            if USE_NEW_AGENTS:
                try:
                    from agents.base_agent import AgentConfig
                    model_name = AgentConfig().model
                except:
                    pass

            self.send_json({
                'status': 'success',
                'using_new_agents': USE_NEW_AGENTS,
                'database_available': db is not None,
                'cli_available': CLAUDE_CLI_AVAILABLE,
                'model': model_name
            })
            return

        # Default static file serving
        return super().do_GET()

    def do_PATCH(self):
        """Handle API PATCH calls for updates."""
        parsed_path = urllib.parse.urlparse(self.path)

        # Update component
        if parsed_path.path.startswith('/api/components/'):
            if not USE_NEW_AGENTS or not api:
                self.send_json({'status': 'error', 'message': 'Database not available'}, 503)
                return

            component_id = parsed_path.path.split('/')[-1]
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                updates = json.loads(post_data.decode('utf-8'))
                result = api.update_component(component_id, updates)
                self.send_json(result)
            except Exception as e:
                self.send_json({'status': 'error', 'message': str(e)}, 500)
            return

        # Update project
        if parsed_path.path.startswith('/api/projects/'):
            if not USE_NEW_AGENTS or not api:
                self.send_json({'status': 'error', 'message': 'Database not available'}, 503)
                return

            project_id = parsed_path.path.split('/')[-1]
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                updates = json.loads(post_data.decode('utf-8'))
                result = api.update_project(project_id, updates)
                self.send_json(result)
            except Exception as e:
                self.send_json({'status': 'error', 'message': str(e)}, 500)
            return

        self.send_error(404, "Endpoint not found")

    def do_DELETE(self):
        """Handle API DELETE calls."""
        parsed_path = urllib.parse.urlparse(self.path)

        # Delete project
        if parsed_path.path.startswith('/api/projects/'):
            if not USE_NEW_AGENTS or not db:
                self.send_json({'status': 'error', 'message': 'Database not available'}, 503)
                return

            project_id = parsed_path.path.split('/')[-1]
            try:
                success = db.delete_project(project_id)
                if success:
                    print(f"[Server] Deleted project: {project_id}")
                    self.send_json({'status': 'success', 'message': 'Project deleted'})
                else:
                    self.send_json({'status': 'error', 'message': 'Project not found'}, 404)
            except Exception as e:
                print(f"[Server] Error deleting project: {e}")
                self.send_json({'status': 'error', 'message': str(e)}, 500)
            return

        self.send_error(404, "Endpoint not found")

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def send_json(self, data, code=200):
        """Send a JSON response."""
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')  # Allow CORS
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))


# Reuse address to prevent "Address already in use" on restarts
socketserver.TCPServer.allow_reuse_address = True

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), AgenticHandler) as httpd:
        print(f"\n{'='*60}")
        print(f"  Agent Orchestrator Server")
        print(f"  Running at http://localhost:{PORT}")
        print(f"{'='*60}")
        print(f"\nAgent Mode: {'Claude Code CLI' if USE_NEW_AGENTS else 'Legacy (Heuristics)'}")
        print(f"\nPhase 1 - Interview Endpoints:")
        print(f"  POST /api/start_interview      - Start new project interview")
        print(f"  POST /api/refine_interview     - Refine with answers to questions")
        print(f"\nPhase 2 - Architecture Endpoints:")
        print(f"  POST /api/projects/<id>/architecture - Generate architecture")
        print(f"  POST /api/projects/<id>/approve      - Approve and advance phase")
        print(f"  POST /api/analyze                    - Analyze codebase")
        print(f"\nData Endpoints:")
        print(f"  GET  /api/projects             - List all projects")
        print(f"  GET  /api/projects/<id>/graph  - Get project graph data")
        print(f"  GET  /api/components/<id>      - Get component details")
        print(f"  GET  /api/agents               - List all agents")
        print(f"  PATCH /api/components/<id>     - Update component")
        print(f"  PATCH /api/projects/<id>       - Update project")
        print(f"\nUtility Endpoints:")
        print(f"  GET  /api/status               - Server status")
        print(f"  GET  /open?path=<path>         - Open file in editor")
        print(f"\n{'='*60}\n")
        httpd.serve_forever()
