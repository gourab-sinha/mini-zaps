# run.py
#!/usr/bin/env python3
"""
Simple script to run the Mini-Zaps server
Place this in the project root directory
"""

import uvicorn

if __name__ == "__main__":
    print("🚀 Starting Mini-Zaps Workflow Builder...")
    print("📖 API Documentation: http://localhost:8000/docs")
    print("🏥 Health Check: http://localhost:8000")
    print("\nPress Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )

