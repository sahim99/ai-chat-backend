import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from database import create_session, log_event, end_session, update_session_summary, get_session_events, supabase
from llm_service import generate_response, generate_summary

app = FastAPI()

def determine_system_prompt(user_message: str) -> str:
    """
    Analyzes the user's message to determine the most suitable system persona.
    Returns a specific prompt instruction based on detected keywords.
    """
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
    """
    Background task to generate and save a summary of the completed session.
    Fetches the full event history, constructs a transcript, and updates the database.
    """
    print(f"Starting background summary for session {session_id}...")
    try:
        events = await get_session_events(session_id)
        
        # Reconstruct the conversation transcript from the stored events
        transcript = ""
        for ev in events:
            etype = ev.get("type")
            payload = ev.get("payload")
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
    """
    Main WebSocket endpoint for handling real-time AI chat sessions.
    
    Responsibilities:
    1. Manage WebSocket connection lifecycle (accept/close).
    2. Initialize or resume session state in the database.
    3. Handle real-time message exchange and persistence.
    4. Maintain conversation context for the LLM.
    5. Stream LLM responses back to the client.
    """
    await websocket.accept()
    
    # Initialize or resume the session in the database.
    # We use upsert to ensure we handle both new sessions and reconnections gracefully.
    try:
        data = {
            "session_id": session_id,
            "user_id": "anonymous_user",  # Could be dynamic based on auth in the future
            "start_time": "now()"
        }
        supabase.table("sessions").upsert(data).execute()
        print(f"Session {session_id} initialized/resumed.")
    except Exception as e:
        print(f"Error creating session: {e}")
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_text()
            
            # 1. Persist the incoming user message
            await log_event(session_id, "user_message", {"text": data})
            
            # 2. Determine the appropriate AI persona based on the message content
            system_prompt = determine_system_prompt(data)
            
            # 3. Build Conversation Context (Memory)
            # Retrieve recent history to provide context to the LLM
            try:
                history_events = await get_session_events(session_id)
                # Exclude the current message (which was just logged) to prevent duplication if the DB query captures it
                relevant_history = history_events[:-1] if history_events else [] 
                
                # Limit context to the last 10 interactions to manage token usage
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

            # 4. Generate Response using the LLM Service
            response_text = await generate_response(full_prompt, system_prompt=system_prompt)
            
            # 5. Stream the response back to the client
            # Currently simulating streaming by chunking the complete response.
            # In a production environment with a streaming-capable LLM, this should stream tokens directly.
            chunk_size = 4
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i+chunk_size]
                await websocket.send_text(chunk)
                await asyncio.sleep(0.01) # Small delay for visual effect
            
            # 6. Persist the AI's response
            await log_event(session_id, "ai_response", {"text": response_text})
            
    except WebSocketDisconnect:
        print(f"Client disconnected {session_id}")
        await end_session(session_id)
        
        # Trigger background summarization task upon session end
        asyncio.create_task(run_summarization(session_id))
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        await websocket.close()
