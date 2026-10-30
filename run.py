import uvicorn
from pathlib import Path

if __name__ == "__main__":
    print("Starting ReliefRadar...")
    print("Dashboard: http://127.0.0.1:8000")
    print("API docs: http://127.0.0.1:8000/docs")

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )