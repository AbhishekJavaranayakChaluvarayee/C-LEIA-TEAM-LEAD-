import uuid
import requests

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

# Configuration
DATABASE_URL = "mysql+pymysql://root:fahim1234@localhost/cleia_db"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

# Database Setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="C-LEIA API", description="Requirements Elicitation Learning with AI")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class StartSessionRequest(BaseModel):
    domain_id: int
    persona_id: int
    student_id: Optional[str] = None

class SessionResponse(BaseModel):
    session_id: str
    domain: dict
    persona: dict

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    reply: str

class SolutionSubmission(BaseModel):
    session_id: str
    solution_type: str
    solution_content: str

class Domain(BaseModel):
    id: int
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True

class Persona(BaseModel):
    id: int
    name: str
    role: str
    background_story: str

    class Config:
        from_attributes = True
class PersonaCreateRequest(BaseModel):
    domain_id: int                  # You can hardcode 1 if you have only one domain
    name: str                      # Persona Name
    role: str                      # Business Name
    background_story: str          # Business Description
    personality_traits: str 
# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper Functions
def save_message_to_db(session_id: str, sender: str, message: str, db: Session):
    """Save a conversation message to the database."""
    try:
        # Get persona_id from session
        session_query = text("SELECT persona_id FROM student_sessions WHERE session_id = :session_id")
        session_result = db.execute(session_query, {"session_id": session_id}).fetchone()
        if not session_result:
            raise HTTPException(status_code=404, detail="Session not found")
        persona_id = session_result[0]
        query = text("""
            INSERT INTO conversations (session_id, persona_id, sender, message)
            VALUES (:session_id, :persona_id, :sender, :message)
        """)
        db.execute(query, {
            "session_id": session_id,
            "persona_id": persona_id,
            "sender": sender,
            "message": message
        })
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving message: {e}")
        raise HTTPException(status_code=500, detail="Could not save message")

def call_ollama_api(session_id: str, user_message: str, db: Session) -> str:
    """
    Call Ollama API with persona context and conversation history,
    using the persona linked to the given session_id.
    """

    try:
        # Fetch persona info linked to session
        query = text("""
            SELECT 
                p.initial_prompt, 
                p.background_story, 
                p.name, 
                p.role,
                p.personality_traits
            FROM student_sessions s
            JOIN personas p ON s.persona_id = p.id
            WHERE s.session_id = :session_id
        """)
        result = db.execute(query, {"session_id": session_id}).fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Session not found or persona missing")

        initial_prompt, background_story, persona_name, persona_role, personality_traits = result

        # Get conversation history for this session
        history_query = text("""
            SELECT sender, message FROM conversations
            WHERE session_id = :session_id ORDER BY created_at ASC
        """)
        history_results = db.execute(history_query, {"session_id": session_id}).fetchall()

        # Build detailed system prompt using all persona info dynamically
        system_prompt = f"""
{initial_prompt}

IMPORTANT CONTEXT:
- You are {persona_name}, a {persona_role}
- Personality traits: {personality_traits or "No specific traits provided"}
- Background: {background_story}

This is a requirements elicitation exercise where a student is learning to gather business requirements.
The student should discover your needs through questioning.
Be realistic about your business constraints and priorities.
Don't volunteer all information at once - let the student ask good questions.
If asked about technical implementation, redirect to your business needs.
Stay in character throughout the conversation.
"""

        # Aggregate full prompt including conversation history
        full_prompt = system_prompt + "\n\nConversation History:\n"
        for sender, msg in history_results:
            full_prompt += f"{sender}: {msg}\n"
        full_prompt += f"student: {user_message}\npersona:"

        # Prepare payload for Ollama API
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False
        }

        # Call Ollama API and get response
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        response_data = response.json()

        ai_reply = response_data.get("message", {}).get("content") or response_data.get("response", "")
        if not ai_reply:
            print("DEBUG Ollama raw response:", response_data)
            raise HTTPException(status_code=502, detail="No response from LLM/Ollama")

        return ai_reply

    except requests.exceptions.RequestException as e:
        print(f"Ollama API error: {e}")
        raise HTTPException(status_code=503, detail="AI service unavailable")

    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Error processing AI response")

# API Endpoints

@app.get("/")
def read_root():
    return {"status": "C-LEIA API is running", "version": "1.0"}

@app.get("/api/domains", response_model=List[Domain])
def get_domains(db: Session = Depends(get_db)):
    """Get all available business domains."""
    try:
        query = text("SELECT id, name, description FROM domains")
        results = db.execute(query).fetchall()
        # Convert results to list of dicts
        return [ {"id": row[0], "name": row[1], "description": row[2]} for row in results ]
    except Exception as e:
        print(f"Error fetching domains: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch domains")

@app.get("/api/domains/{domain_id}/personas", response_model=List[Persona])
def get_personas_for_domain(domain_id: int, db: Session = Depends(get_db)):
    """Get all personas for a specific domain."""
    try:
        query = text("""
            SELECT id, name, role, background_story
            FROM personas WHERE domain_id = :domain_id
        """)
        results = db.execute(query, {"domain_id": domain_id}).fetchall()
        # IMPORTANT: Make sure the response matches Persona model fields!
        # If the returned rows are: id, name, role, background_story
        # and Persona expects same, this works.
        return [
            {"id": row[0], "name": row[1], "role": row[2], "background_story": row[3]}
            for row in results
        ]
    except Exception as e:
        print(f"Error fetching personas: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch personas")

@app.post("/api/start_session", response_model=SessionResponse)
def start_new_session(request: StartSessionRequest, db: Session = Depends(get_db)):
    """Start a new requirements elicitation session."""
    try:
        session_id = str(uuid.uuid4())
        # Create session record
        session_query = text("""
            INSERT INTO student_sessions (session_id, student_id, domain_id, persona_id)
            VALUES (:session_id, :student_id, :domain_id, :persona_id)
        """)
        db.execute(session_query, {
            "session_id": session_id,
            "student_id": request.student_id,
            "domain_id": request.domain_id,
            "persona_id": request.persona_id
        })
        # Get domain and persona details
        details_query = text("""
            SELECT d.name as domain_name, d.description as domain_desc,
                   p.name as persona_name, p.role as persona_role, p.background_story
            FROM domains d, personas p
            WHERE d.id = :domain_id AND p.id = :persona_id
        """)
        result = db.execute(details_query, {
            "domain_id": request.domain_id,
            "persona_id": request.persona_id
        }).fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Domain or persona not found")
        db.commit()
        return {
            "session_id": session_id,
            "domain": {"name": result[0], "description": result[1]},
            "persona": {"name": result[2], "role": result[3], "background_story": result[4]}
        }
    except Exception as e:
        db.rollback()
        print(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail="Could not start session")

@app.post("/api/chat", response_model=ChatResponse)
def handle_chat_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Handle a chat message in a requirements elicitation session."""
    try:
        # Save student message
        save_message_to_db(request.session_id, "student", request.message, db)
        # Get AI response
        ai_reply = call_ollama_api(request.session_id, request.message, db)
        # Save AI response
        save_message_to_db(request.session_id, "persona", ai_reply, db)
        return {"reply": ai_reply}
    except Exception as e:
        print(f"Error handling chat: {e}")
        raise HTTPException(status_code=500, detail="Error processing message")

@app.post("/api/submit_solution")
def submit_solution(request: SolutionSubmission, db: Session = Depends(get_db)):
    """Submit a solution (requirements document, diagram, etc.)."""
    try:
        query = text("""
            INSERT INTO student_solutions (session_id, solution_type, solution_content)
            VALUES (:session_id, :solution_type, :solution_content)
        """)
        db.execute(query, {
            "session_id": request.session_id,
            "solution_type": request.solution_type,
            "solution_content": request.solution_content
        })
        db.commit()
        return {"message": "Solution submitted successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error submitting solution: {e}")
        raise HTTPException(status_code=500, detail="Could not submit solution")

@app.get("/api/export/conversations/{session_id}")
def export_conversation(session_id: str, db: Session = Depends(get_db)):
    """Export conversation for analysis (anonymized)."""
    try:
        query = text("""
            SELECT c.sender, c.message, c.created_at,
                   p.name as persona_name, p.role as persona_role,
                   d.name as domain_name
            FROM conversations c
            JOIN student_sessions s ON c.session_id = s.session_id
            JOIN personas p ON c.persona_id = p.id
            JOIN domains d ON s.domain_id = d.id
            WHERE c.session_id = :session_id
            ORDER BY c.created_at ASC
        """)
        results = db.execute(query, {"session_id": session_id}).fetchall()
        conversation_data = {
            "domain": results[0][5] if results else None,
            "persona": {"name": results[0][3], "role": results[0][4]} if results else None,
            "messages": [
                {"sender": row[0], "message": row[1], "timestamp": row[2].isoformat()}
                for row in results
            ]
        }
        return conversation_data
    except Exception as e:
        print(f"Error exporting conversation: {e}")
        raise HTTPException(status_code=500, detail="Could not export conversation")

# Serve static files (like CSS or JS) if needed
app.mount("/static", StaticFiles(directory="Frontendd"), name="static")

# Serve the HTML chat UI
@app.get("/chat-ui")
def serve_chat_ui():
    file_path = os.path.join("Frontendd", "NewChatpage.html")
    return FileResponse(file_path)
@app.get("/newform")
def serve_newform():
    return FileResponse(os.path.join("Frontendd", "Newformpage.html"))


@app.post("/api/persona")
def create_persona(data: PersonaCreateRequest, db: Session = Depends(get_db)):
    try:
        stmt = text("""
            INSERT INTO personas (
                domain_id, name, role, background_story, initial_prompt, personality_traits
            ) VALUES (
                :domain_id, :name, :role, :background_story, '', :personality_traits
            )
        """)
        db.execute(stmt, {
            "domain_id": data.domain_id,
            "name": data.name,
            "role": data.role,
            "background_story": data.background_story,
            "personality_traits": data.personality_traits
        })
        persona_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        db.commit()
        return {"message": "Persona created successfully", "persona_id": persona_id}
    except Exception as e:
        db.rollback()
        print(f"Error creating persona: {e}")
        raise HTTPException(status_code=500, detail="Failed to create persona")