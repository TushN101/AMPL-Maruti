"""
SOQ Alert Dashboard — Minimal Flask Server
Serves static files only. All processing happens client-side.
Deploy to Vercel with vercel-serverless or any static host.
"""

from flask import Flask, render_template , request
from supabase import create_client , Client
from dotenv import load_dotenv
import os

app = Flask(__name__)

## -- spazy ---
## -- start of code -- 
load_dotenv()

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY")
)

project_slug = "ampl"

@app.before_request
def spazzy():
    try:
        if "static" not in request.path:
            _ = supabase.table("logs").insert({
                "visited_proj": project_slug,
                "visited_route": request.path,
                "remote_ip": request.headers.get("x-real-ip") or "",
                "remote_ua": request.headers.get('User-Agent') or ""
            }).execute()
    except Exception as e:
        print(f"[Error] Failed to send data  {e}")
        pass    
# -- end of code --    

@app.route('/')
def index():
    return render_template("index.html")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
