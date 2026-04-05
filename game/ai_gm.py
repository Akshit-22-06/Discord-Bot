import os
import google.generativeai as genai
from core.config import GEMINI_API_KEY
from database.db import get_past_stories

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

def generate_night_story(killed_players: list[str], healed_players: list[str], day_num: int) -> str:
    """Generates a dynamic story for what happened during the night."""
    if not model:
        if killed_players:
            return f"The morning arrives. Sadly, {', '.join(killed_players)} was found dead."
        return "The morning arrives. Everyone woke up safely."

    # Add self-learning context to improve stories (e.g. referencing tone)
    past_stories = get_past_stories()
    learning_context = ""
    # In a full implementation, we would extract the sentiment and ask the AI to evolve the narrative style.
    
    system_prompt = "You are the Game Master for a game of Mafia. You narrate the events of the night in a dramatic, suspenseful tone. Keep it under 3 paragraphs. You should focus on setting the scene."
    
    if killed_players:
        user_prompt = f"It is the dawn of Day {day_num}. The mafia attacked and successfully killed {', '.join(killed_players)}. Tell the town what they woke up to."
    elif healed_players:
        user_prompt = f"It is the dawn of Day {day_num}. The mafia attempted an attack, but the doctor miraculously saved the target. Tell the town what happened without revealing the target's name."
    else:
        user_prompt = f"It is the dawn of Day {day_num}. The night was peaceful. No one was attacked."

    prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI Generation Error: {e}")
        if killed_players:
            return f"The town wakes up to find {', '.join(killed_players)} dead."
        return "The town wakes up safely."
