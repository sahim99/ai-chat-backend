import os
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

supabase: Client = create_client(url, key)

async def create_session(user_id: str = "anonymous") -> str:
    """Creates a new session and returns the session_id."""
    data = {
        "user_id": user_id,
        "start_time": datetime.now(timezone.utc).isoformat(),
    }
    response = supabase.table("sessions").insert(data).execute()
    # response.data is a list of dicts
    if response.data:
        return response.data[0]["session_id"]
    raise Exception("Failed to create session")

async def log_event(session_id: str, event_type: str, payload: dict):
    """Logs an event to the events table."""
    data = {
        "session_id": session_id,
        "type": event_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    # Fire and forget
    supabase.table("events").insert(data).execute()

async def end_session(session_id: str):
    """Updates the session with end_time."""
    data = {
        "end_time": datetime.now(timezone.utc).isoformat()
    }
    supabase.table("sessions").update(data).eq("session_id", session_id).execute()

async def update_session_summary(session_id: str, summary: str):
    """Updates the session with the generated summary."""
    supabase.table("sessions").update({"summary": summary}).eq("session_id", session_id).execute()

async def get_session_events(session_id: str):
    """Fetches all events for a session, ordered by time."""
    response = supabase.table("events").select("*").eq("session_id", session_id).order("timestamp").execute()
    return response.data
