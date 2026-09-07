from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, FileResponse
from api.routes import auth, files, ai, quiz, admin
from bot.database.engine import init_db

app = FastAPI(title="EduBot API")

# Gzip compression for high-speed transmission to mobile devices
app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CacheControlMiddleware(BaseHTTPMiddleware):
    """Add caching headers for static assets so mobile devices cache scripts and CSS locally."""
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        if path.endswith(".js") or path.endswith(".css") or path.endswith(".html") or path == "/":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif any(path.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".ico", ".woff", ".woff2", ".ttf"]):
            response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=43200"
        return response

app.add_middleware(CacheControlMiddleware)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["quiz"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/behruz620sh")
async def admin_panel_page():
    """Direct secret access route for Admin Panel requested by owner."""
    return FileResponse("webapp/admin.html")

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
