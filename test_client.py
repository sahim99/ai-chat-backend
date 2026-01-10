import asyncio
import websockets
import uuid
import sys

SESSION_ID = str(uuid.uuid4())
URL = f"ws://localhost:8000/ws/session/{SESSION_ID}"

async def test_session():
    print(f"Connecting to {URL}...")
    try:
        async with websockets.connect(URL) as websocket:
            print("Connected.")
            
            # Test 1: Simple greeting (Default Intent)
            msg1 = "Hello, who are you?"
            print(f"> Sending: {msg1}")
            await websocket.send(msg1)
            
            print("< Receiving response:")
            while True:
                try:
                    # We utilize a timeout to detect end of stream if server doesn't send explicit end message
                    # Our server just stops sending. 
                    # But 'recv' waits forever.
                    # In a real app, backend sends a specialized "end-of-stream" token or we detect silence.
                    # For this test, we just wait a bit and break?
                    # Or simpler: The backend simulates streaming then stops.
                    # The demo code in main.py loops forever waiting for next user message.
                    # So we can't easily know when AI is done without a delimiter.
                    # Let's just read N times or set a timeout.
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    sys.stdout.write(response)
                    sys.stdout.flush()
                except asyncio.TimeoutError:
                    print("\n[Timeout] AI likely finished response.")
                    break
            
            # Test 2: Intent Switch (Python)
            msg2 = "Write a Python function to add two numbers."
            print(f"\n> Sending: {msg2}")
            await websocket.send(msg2)
            
            print("< Receiving response:")
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    sys.stdout.write(response)
                    sys.stdout.flush()
                except asyncio.TimeoutError:
                    print("\n[Timeout] AI likely finished response.")
                    break
                    
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_session())
