import sys
import os
import uvicorn

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    uvicorn.run("backend.api.main:app", host="127.0.0.1", port=8008, reload=True)
