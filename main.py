import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from database import create_session, log_event, end_session, update_session_summary, get_session_events
from llm_service import generate_response, generate_summary

app = FastAPI()

# Intent Detection Logic
def determine_system_prompt(user_message: str) -> str:
    msg_lower = user_message.lower()
    if any(k in msg_lower for k in ["code", "python", "bug", "function", "variable"]):
        return "You are an expert Python programmer. Provide efficient, clean, and well-documented code."
    elif any(k in msg_lower for k in ["summary", "recap", "tl;dr"]):
        return "You are a concise summarizer. distilling complex information into key bullet points."
    elif any(k in msg_lower for k in ["story", "creative", "write a poem"]):
        return "You are a creative writer. Use vivid imagery and engaging narrative structures."
    else:
        return "You are a helpful AI assistant."

async def run_summarization(session_id: str):
    """Background task to summarize the session."""
    print(f"Starting background summary for session {session_id}...")
    try:
        events = await get_session_events(session_id)
        # Construct conversation history
        # events is a list of dicts (from Supabase response)
        # Format: User: ... \n AI: ...
        transcript = ""
        for ev in events:
            etype = ev.get("type")
            payload = ev.get("payload")
            # payload is stored as jsonb, so it comes back as dict
            # or logic depending on how we stored it. 
            # In log_event we passed a dict.
            # Let's assume payload has 'text' field.
            content = payload.get("text", "") if isinstance(payload, dict) else str(payload)
            
            if etype == "user_message":
                transcript += f"User: {content}\n"
            elif etype == "ai_response":
                transcript += f"AI: {content}\n"
        
        if not transcript.strip():
            print(f"No transcript to summarize for {session_id}")
            return

        summary = await generate_summary(transcript)
        await update_session_summary(session_id, summary)
        print(f"Summary completed for {session_id}")
    except Exception as e:
        print(f"Error in background summary for {session_id}: {e}")

@app.websocket("/ws/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    # Create session in DB (or verify if exists?)
    # For this demo, we assume the frontend generates a session_id or we treat this connection as the *start* of that session.
    # But ideally, 'create_session' makes a new ID. 
    # If the URL implies an existing ID, we might need to handle that.
    # The user requirements say "/ws/session/{session_id}".
    # Let's assume the frontend passes a UUID.
    # We will try to create a *new* session entry for this connection, or update if it exists?
    # Schema has 'session_id' as PK. Creating a dupe will fail.
    # Let's rely on the frontend generating a unique ID per session, 
    # OR we treat the session_id in URL as a 'room' and we create a 'connection' record?
    # The requirement says: "1. Client connects -> FastAPI creates a session row."
    # So we should create the row here.
    # BUT if the ID is in the URL, the client picked it?
    # Let's assume client picked it (UUID v4).
    # We try to insert. If it exists, maybe we just continue (reconnection).
    # But for a simpler flow: Client generates ID -> Connects.
    
    # Actually, simpler: Ignore the URL param for DB creation if we can't control it, 
    # OR just use it. Let's use it.
    
    # Wait, 'create_session' in database.py generates a new specific row. 
    # If we want to use the passed ID, we need to modify 'create_session'.
    # Let's modify 'create_session' to accept an optional ID, or just create one and tell the client?
    # User req: "wss://api.../ws/session/{session_id}"
    # This implies the session ID is known.
    # Let's try to create a session with this ID. If it fails (exists), we assume we are joining it.
    
    # We need to update database.py to allow passing session_id
    # But first let's just accept the connection.
    
    # We will Create a Session Wrapper.
    # Actually, let's just create a new row with this ID.
    try:
        # We need to modify database.py to allow inserting a specific session_id
        # For now, let's assume create_session generates one, which mismatches the URL param concept.
        # FIX: Let's assume the URL param IS the session ID the client wants to use.
        # We should probably check if it exists.
        pass 
    except Exception as e:
        print(f"DB Init error: {e}")

    # Let's do a workaround: The backend creates the session and we ignore the URL param? 
    # No, that breaks the API contract.
    # Let's assume the client sends a UUID.
    
    # Revised flow:
    # 1. Connect.
    # 2. Start Session in DB (upsert).
    
    active_session_id = session_id
    # We might need to manually insert with this ID.
    # Since I can't easily edit database.py right now without another tool call, 
    # I will do a quick raw insert here via the 'supabase' client or just use 'create_session' and ignore the mismatch?
    # No, I should fix it.
    
    # Let's just create a valid session for this interaction.
    # I'll modify database.py or just access supabase directly here.
    # I'll access directly for the specific "insert with ID" logic.
    from database import supabase
    
    try:
        data = {
            "session_id": active_session_id,
            "user_id": "anonymous_user", # or from query param
            "start_time": "now()"
        }
        # Upsert=True in case of reconnection?
        supabase.table("sessions").upsert(data).execute()
        print(f"Session {active_session_id} initialized/resumed.")
    except Exception as e:
        print(f"Error creating session: {e}")
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_text()
            
            # 1. Log User Message
            await log_event(active_session_id, "user_message", {"text": data})
            
            # 2. Determine Intent
            system_prompt = determine_system_prompt(data)
            
            # 3. Build Conversation Context (Memory)
            try:
                history_events = await get_session_events(active_session_id)
                # Keep last 10 events for context, excluding the current one we just logged
                # (Supabase insert is awaited, so it is likely in the list)
                relevant_history = history_events[:-1] if history_events else [] 
                
                # Take only last 10 of the history
                recent_history = relevant_history[-10:]
                
                context_str = ""
                for ev in recent_history:
                    role = "user" if ev["type"] == "user_message" else "assistant"
                    content = ev["payload"].get("text", "")
                    context_str += f"{role}: {content}\n"
                
                if context_str:
                    full_prompt = f"Context (Previous Conversation):\n{context_str}\nUser:\n{data}"
                else:
                     full_prompt = data
            except Exception as e:
                print(f"Memory fetch error: {e}")
                full_prompt = data

            # 4. Call LLM
            response_text = await generate_response(full_prompt, system_prompt=system_prompt)
            
            # 4. Stream response (Simulated)
            chunk_size = 4
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i+chunk_size]
                await websocket.send_text(chunk)
                await asyncio.sleep(0.01) # Small delay to simulate typing
            
            # 5. Log AI Response
            await log_event(active_session_id, "ai_response", {"text": response_text})
            
    except WebSocketDisconnect:
        print(f"Client disconnected {active_session_id}")
        await end_session(active_session_id)
        
        # Trigger background summary
        # We need a way to run background tasks.
        # In a WebSocket endpoint, we don't have 'BackgroundTasks' object passed in like HTTP.
        # We have to hook into the event loop or use a global manager.
        # asyncio.create_task is sufficient for fire-and-forget in this scope?
        # Yes, asyncio.create_task(run_summarization(active_session_id))
        asyncio.create_task(run_summarization(active_session_id))
        
    except Exception as e:
        print(f"Error: {e}")
        await websocket.close()

