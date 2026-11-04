"""
Development runner for FastAPI application.
Restricts Uvicorn auto-reload to application code ('app/'), ensuring WatchFiles
never reloads upon student file uploads or extraction in 'uploads/'.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["app"],
    )
