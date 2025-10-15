import os
import json
from typing import List, Dict, Union

# Import the Google GenAI library
from google import genai
from google.genai import types

# Initialize the client (Reads GEMINI_API_KEY from environment variables)
client = genai.Client()


# 1. Define the Function/Tool Schema (Forces structured output for escalation)
ESCALATION_TOOL_SCHEMA = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name='escalate_to_human',
            description='Triggers a handoff to a human representative for complex, urgent, or account-specific issues.',
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "summary": types.Schema(
                        type=types.Type.STRING,
                        description="A brief, one-sentence summary of the user's core problem for the human agent."
                    )
                },
                required=['summary'],
            ),
        )
    ]
)


# 2. System Prompt (Simplified for Tool Use - No JSON instruction needed)
SYSTEM_PROMPT = """
You are 'Alina', a friendly and professional customer support agent for a leading tech company called 'Unthinkable'. 
Your primary function is to answer common customer FAQs concisely and accurately.

**CRITICAL RULE:** If the user's query is complex, involves account-specific data, or uses strong keywords for human help (like 'escalate', 'speak to manager', 'account access', 'talk to agent', 'urgent'), you MUST invoke the 'escalate_to_human' tool immediately.
"""


def generate_llm_response(history: List[Dict[str, str]], new_query: str) -> Union[str, Dict[str, Union[bool, str]]]:
    """
    Sends the conversation history and new query to the Gemini API using the Tool Calling method
    to enforce structured escalation output.
    """
    
    # Prepare history for the conversation structure
    messages = []

    # Inject the system persona and initial greeting for context establishment
    messages.append(types.Content(role="user", parts=[types.Part.from_text(text=SYSTEM_PROMPT)]))
    messages.append(types.Content(role="model", parts=[types.Part.from_text(text="Hello! I am Alina. How can I assist you today?")]))

    # Map previous turns
    for message in history:
        # Map assistant role to 'model' for Gemini
        # FIX: Ensure non-assistant role maps correctly to 'user'
        role = 'model' if message['role'] == 'assistant' else 'user'
        messages.append(types.Content(role=role, parts=[types.Part.from_text(text=message['content'])]))

    # Add the current user query
    messages.append(types.Content(role='user', parts=[types.Part.from_text(text=new_query)]))

    try:
        # 3. Call the Gemini API with the Tool/Function
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=messages,
            config=types.GenerateContentConfig(
                temperature=0.0,
                tools=[ESCALATION_TOOL_SCHEMA],  # Provide the tool schema to force structure
            )
        )
        
        # 4. Check the response for a function call (the escalation trigger)
        if response.function_calls:
            call = response.function_calls[0]
            if call.name == 'escalate_to_human':
                # The model successfully invoked the tool!
                summary = call.args.get('summary', "Issue requires immediate human attention.")
                
                return {
                    "escalate": True,
                    "summary": summary
                }
        
        # 5. Normal conversational response (if no function call)
        return response.text.strip()

    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "I apologize, Alina is currently experiencing connection issues. Please try again later."


def summarize_conversation(history: List[Dict[str, str]]) -> str:
    """Uses the Gemini API to summarize the entire conversation for the human agent."""
    if not history:
        return "No conversation history available."

    # Prompt the LLM specifically for summarization
    # FINAL FIX: Remove the 'senior support lead' persona and force factual output.
    summary_prompt = "You are a neutral assistant. Summarize the user's core, unfulfilled request in the conversation below into a single, concise sentence for a human agent. Do not critique the bot's actions or use bullet points.\n\n"
    for msg in history:
        summary_prompt += f"[{msg['role'].upper()}]: {msg['content']}\n"

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[types.Content(role='user', parts=[types.Part.from_text(text=summary_prompt)])],
            config=types.GenerateContentConfig(temperature=0.0)
        )
        return response.text.strip()
    except Exception as e:
        return "Summary generation failed."