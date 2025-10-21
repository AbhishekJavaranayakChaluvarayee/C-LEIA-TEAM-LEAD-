import requests
from sqlalchemy import create_engine, text

# --- Configuration ---
DATABASE_URL = "mysql+pymysql://root@localhost/cleia_db"  # adjust password if needed
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

# --- Connect to Database ---
engine = create_engine(DATABASE_URL)

def get_persona(persona_id=1):
    """
    Fetch persona info from the database by persona_id.
    """
    with engine.connect() as conn:
        query = text("""
            SELECT name, personality_traits, background_story
            FROM personas
            WHERE id = :persona_id
        """)
        result = conn.execute(query, {"persona_id": persona_id}).fetchone()
        if not result:
            raise Exception(f"Persona with ID {persona_id} not found.")
        return {
            "name": result[0],
            "style": result[1],
            "business_description": result[2]
        }

def format_prompt(question, persona_data):
    return f"""
You are {persona_data['name']}, {persona_data['style']}.
Here is the business model you are helping:
{persona_data['business_description']}

Now, respond to this user question in a helpful tone:
{question}
"""

def ask_ollama(prompt, model="mistral"):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        print("❌ Error:", e)
        return ""

def chat(persona_id=1):
    """
    Start an interactive chat with a persona from the database.
    """
    try:
        persona_data = get_persona(persona_id)
    except Exception as e:
        print(f"❌ Cannot start chat: {e}")
        return

    print(f"\n🤖 You are now chatting with {persona_data['name']}.\n")

    while True:
        question = input("You: ")
        if question.lower() in ["exit", "quit"]:
            break
        prompt = format_prompt(question, persona_data)
        answer = ask_ollama(prompt)
        print(f"\n{persona_data['name']}: {answer}\n")


if __name__ == "__main__":
    chat(persona_id=1)  # You can change this ID to load a different persona
