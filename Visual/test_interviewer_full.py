
import os
import sys
import json
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Check dependencies
if not shutil.which('claude'):
    print("SKIPPING: 'claude' CLI not not found in PATH.")
    sys.exit(0)

# Mock env setup - ensure we use CLI
os.environ['USE_CLAUDE_CLI'] = 'true'

try:
    from db import Database
    from agents import InterviewerAgent
except ImportError as e:
    print(f"ERROR: Could not import agents: {e}")
    sys.exit(1)

def test_interviewer_flow():
    print("Initializing Database...")
    try:
        # Use in-memory DB for test
        db = Database(":memory:")
    except Exception as e:
         print(f"DB Init Failed: {e}")
         # Fallback to dummy
         class DummyDB:
             def get_project(self, *args): return None
             def create_project(self, *args, **kwargs): return type('obj', (object,), {'id': 'test_proj', 'name': 'Test', 'summary': '', 'problem': '', 'phase': ''})
             def create_component(self, *args, **kwargs): pass
             def create_edge(self, *args, **kwargs): pass
             def create_global_task(self, *args, **kwargs): pass
             def create_agent(self, *args, **kwargs): pass
             def create_log(self, *args, **kwargs): print(f"LOG: {kwargs.get('message')}")
         db = DummyDB()

    print("Initializing InterviewerAgent...")
    agent = InterviewerAgent(db)
    
    prompt = "I want to build a simple CLI todo app in Python"
    print(f"\nExecuting Interview with prompt: '{prompt}'")
    print("(This may take 10-20 seconds via Claude CLI...)")
    
    try:
        brief = agent.execute(prompt)
        
        print("\n--- BRIEF GENERATED ---")
        print(f"Title: {brief.get('title')}")
        print(f"Summary: {brief.get('summary')}")
        print(f"Components: {len(brief.get('components', []))}")
        
        labels = [c.get('label') for c in brief.get('components', [])]
        print(f"Component Labels: {labels}")
        
        if len(brief.get('components', [])) > 0:
            print("\n✅ SUCCESS: Brief generated with components.")
        else:
            print("\n⚠️ WARNING: Brief generated but no components found.")
            
    except Exception as e:
        print(f"\n❌ FAILURE: Agent execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_interviewer_flow()
