from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Union
from starlette.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid

# Import custom modules
from memory_handler import save_message, get_context
from llm_service import generate_llm_response, summarize_conversation

app = FastAPI(
    title="Alina Conversational Support Bot",
    description="Backend API with Redis session management and Gemini-driven escalation."
)
origins = [
    "https://alina-ask-assist-bot.onrender.com"
    "https://alinaaaaaa-2003.github.io",
    "http://localhost",
    "http://localhost:8000",
    "null", # Essential for allowing local file system access (file:///index.html)
    "*" # Allows access from any domain when deployed (simplifies testing)
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows POST, GET, OPTIONS, etc.
    allow_headers=["*"], # Allows all headers
)

# Pydantic models for structured data exchange
class ChatRequest(BaseModel):
    session_id: str = None 
    query: str
    
class ChatResponse(BaseModel):
    session_id: str
    response: str
    is_escalated: bool = False
    escalation_summary: str = None

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main endpoint to receive a user query, process it, and return a response.
    Handles context, conversation save, and autonomous escalation.
    """
    
    # 1. Session Management and Input Validation
    session_id = request.session_id if request.session_id else str(uuid.uuid4())
    user_query = request.query.strip()
    
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    # 2. Retrieve Context (Conversational Memory)
    history = get_context(session_id)
    
    # --- NEW: De-escalation Logic ---
    is_currently_escalated = False
    if history and history[-1].get("role") == "assistant" and history[-1].get("type") == "escalation_summary":
        is_currently_escalated = True
    
    # If the session is flagged as recently escalated, we wipe the context passed to the LLM 
    # to force it to treat the new query as a completely new, simple topic (de-escalation).
    if is_currently_escalated:
        history = [] 
    
    # --- End NEW De-escalation Logic ---
    
    # 3. Save User Message to Context (using the new 'type' field)
    save_message(session_id, "user", user_query, type="normal") 
    
    # 4. Generate LLM Response (Calls the Gemini-integrated service)
    llm_output = generate_llm_response(history, user_query)
    
    # 5. Process LLM Output for Escalation
    if isinstance(llm_output, dict) and llm_output.get("escalate") is True:
        # --- Escalation Flow Triggered ---
        
        # Get the full history *again* (including the new user message) for detailed summary
        full_history = get_context(session_id)
        summary = summarize_conversation(full_history)
        
        # IMPORTANT: Save the summary message with the 'escalation_summary' type
        # This flags the session for de-escalation check on the NEXT turn.
        save_message(session_id, "assistant", f"SUMMARY: {summary}", type="escalation_summary")
        
        # Construct the final response to the user
        bot_response = "I see this issue is complex and requires specialized help. Your request has been escalated to a human agent, who has received the following conversation summary for a seamless handoff."
        
        return ChatResponse(
            session_id=session_id,
            response=f"{bot_response}\n\n**Summary for Agent:**\n{summary}",
            is_escalated=True,
            escalation_summary=summary
        )
    
    # 6. Handle Normal Conversational Response
    else:
        bot_response = llm_output
        # Save Bot Message to context as 'normal'
        save_message(session_id, "assistant", bot_response, type="normal")
        
        return ChatResponse(
            session_id=session_id,
            response=bot_response,
            is_escalated=False
        )

# Health Check
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Alina Bot Backend"}
@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    """Redirects the base URL to the interactive documentation."""
    return RedirectResponse(url="/docs") 