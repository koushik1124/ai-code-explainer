import os 
from groq import Groq

def get_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY missing in environment/.env")
    return Groq(api_key=api_key)