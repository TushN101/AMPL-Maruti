"""
SOQ Alert Dashboard — Minimal FastAPI Server
Serves static files and dashboard template. All processing happens client-side.
Deploy to Vercel or any ASGI host.
"""

from pathlib import Path
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTasks
from starlette.concurrency import run_in_threadpool
from starlette.templating import Jinja2Templates
from supabase import create_client, Client
import jinja2
import uvicorn

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="SOQ Alert Dashboard")

# Mount static files directory
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Jinja2 template configuration
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Preserve backward compatibility with Flask's url_for('static', filename='...')
orig_url_for = templates.env.globals["url_for"]


@jinja2.pass_context
def url_for_compat(context: dict, name: str, **path_params):
    _external = path_params.pop("_external", False)
    if name == "static" and "filename" in path_params and "path" not in path_params:
        path_params["path"] = path_params.pop("filename")
    url = orig_url_for(context, name, **path_params)
    if _external:
        return str(url)
    return url.path


templates.env.globals["url_for"] = url_for_compat

## -- Supabase configuration --
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"[Error] Failed to initialize Supabase client: {e}")

project_slug = "ampl"


def _send_analytics_sync(payload: dict) -> None:
    try:
        if supabase is not None:
            _ = supabase.table("logs").insert(payload).execute()
    except Exception as e:
        print(f"[Error] Failed to send data  {e}")


async def _log_analytics_task(payload: dict) -> None:
    await run_in_threadpool(_send_analytics_sync, payload)


## -- Global visitor analytics middleware --
@app.middleware("http")
async def visitor_analytics_middleware(request: Request, call_next):
    path = request.url.path
    is_static = path.startswith("/static") or "static" in path or path == "/favicon.ico"

    response = await call_next(request)

    if not is_static:
        payload = {
            "visited_proj": project_slug,
            "visited_route": path,
            "remote_ip": request.headers.get("x-real-ip") or "",
            "remote_ua": request.headers.get("user-agent") or request.headers.get("User-Agent") or "",
        }

        # Preserve any existing response-level background tasks
        if response.background is None:
            response.background = BackgroundTasks()
        elif not isinstance(response.background, BackgroundTasks):
            response.background = BackgroundTasks([response.background])

        response.background.add_task(_log_analytics_task, payload)

    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
