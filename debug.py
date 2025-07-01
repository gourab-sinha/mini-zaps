# debug.py
"""
Debug script to test Mini-Zaps components individually
Run this to troubleshoot issues
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the current directory to the path
sys.path.append(os.getcwd())

async def test_database():
    """Test database operations"""
    print("🔍 Testing Database...")
    
    try:
        from app.database import Database
        from app.models import WorkflowStatus
        from sqlalchemy import text
        
        db = Database()
        await db.init_db()
        print("✅ Database initialized")
        
        # Test database connection
        async with db.async_session() as session:
            result = await session.execute(text("SELECT 1"))
            print("✅ Database connection test passed")
        
        # Test creating a workflow run
        run = await db.create_workflow_run("test_workflow", {"test": "data"})
        print(f"✅ Created workflow run: {run.id}")
        
        # Test getting the run
        retrieved_run = await db.get_workflow_run(run.id)
        print(f"✅ Retrieved workflow run: {retrieved_run.workflow_name}")
        
        # Test listing runs
        runs = await db.get_workflow_runs(10)
        print(f"✅ Listed {len(runs)} workflow runs")
        
        # Test updating run status
        await db.update_workflow_run(run.id, WorkflowStatus.SUCCEEDED, ["Test log"])
        print("✅ Updated workflow run status")
        
        print("🎉 Database tests passed!\n")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_connectors():
    """Test connector functionality"""
    print("🔍 Testing Connectors...")
    
    try:
        from app.connectors.delay import DelayConnector
        from app.connectors.webhook import WebhookConnector
        
        # Test delay connector
        delay_connector = DelayConnector({"seconds": 1})
        result = await delay_connector.execute({"test": "context"})
        if result.success:
            print("✅ Delay connector works")
        else:
            print(f"❌ Delay connector failed: {result.message}")
            return False
        
        # Test webhook connector schema
        webhook_schema = WebhookConnector.get_config_schema()
        print(f"✅ Webhook connector schema: {len(webhook_schema['properties'])} properties")
        
        print("🎉 Connector tests passed!\n")
        return True
        
    except Exception as e:
        print(f"❌ Connector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_workflow_engine():
    """Test workflow engine"""
    print("🔍 Testing Workflow Engine...")
    
    try:
        from app.workflow_engine import WorkflowEngine
        from app.database import Database
        
        # Create test workflow file
        workflow_dir = Path("workflows")
        workflow_dir.mkdir(exist_ok=True)
        
        test_workflow = """
name: debug_workflow
steps:
  - type: delay
    config:
      seconds: 1
"""
        
        with open(workflow_dir / "debug_workflow.yaml", "w") as f:
            f.write(test_workflow)
        
        db = Database()
        await db.init_db()
        
        engine = WorkflowEngine(db)
        
        # Test loading workflow definition
        workflow_def = await engine.load_workflow_definition("debug_workflow")
        print(f"✅ Loaded workflow: {workflow_def.name} with {len(workflow_def.steps)} steps")
        
        print("🎉 Workflow engine tests passed!\n")
        return True
        
    except Exception as e:
        print(f"❌ Workflow engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_files():
    """Check if all required files exist"""
    print("🔍 Checking Project Structure...")
    
    required_files = [
        "app/__init__.py",
        "app/main.py",
        "app/models.py",
        "app/database.py",
        "app/workflow_engine.py",
        "app/connectors/__init__.py",
        "app/connectors/base.py",
        "app/connectors/delay.py",
        "app/connectors/webhook.py",
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
        else:
            print(f"✅ {file_path}")
    
    if missing_files:
        print(f"\n❌ Missing files:")
        for missing in missing_files:
            print(f"   - {missing}")
        return False
    
    print("🎉 All required files found!\n")
    return True

async def main():
    print("🚀 Mini-Zaps Debug Script")
    print("=" * 40)
    
    # Check project structure
    if not check_files():
        print("Please create the missing files before continuing.")
        return
    
    # Test components
    tests = [
        test_database,
        test_connectors,
        test_workflow_engine
    ]
    
    results = []
    for test in tests:
        result = await test()
        results.append(result)
    
    # Summary
    print("📊 Test Summary:")
    passed = sum(results)
    total = len(results)
    print(f"   ✅ {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your Mini-Zaps installation is working correctly.")
        print("You can now start the server with:")
        print("   poetry run uvicorn app.main:app --reload")
    else:
        print(f"\n❌ {total - passed} tests failed. Please check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())