from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.routes import auth, files, ai, quiz
from bot.database.engine import init_db

app = FastAPI(title="EduBot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["quiz"])

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint for UptimeRobot and monitoring services."""
    return {
        "status": "ok",
        "service": "EduBot",
        "active": True
    }

@app.api_route("/ping", methods=["GET", "HEAD"])
async def ping():
    """Fast ping endpoint for keep-alive bots to prevent Render free-tier sleep."""
    return "pong"

@app.api_route("/keepalive", methods=["GET", "HEAD"])
async def keepalive():
    return {"status": "awake", "message": "Server is up and running"}

app.mount("/", StaticFiles(directory="webapp", html=True), name="webapp")
