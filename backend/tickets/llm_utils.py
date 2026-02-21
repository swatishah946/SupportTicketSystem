import os
import json
import google.generativeai as genai

def classify_ticket(description):
    """
    Classifies a ticket using Google Gemini 2.5 Flash.
    Returns a dictionary with 'suggested_category' and 'suggested_priority'.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"suggested_category": "general", "suggested_priority": "medium", "error": "Missing API Key"}

    try:
        genai.configure(api_key=api_key)
      
        model = genai.GenerativeModel("gemini-2.5-flash") 

        prompt = f"""
        You are a support ticket classification system.
        Analyze the following ticket description and categorize it into one of: 'billing', 'technical', 'account', 'general'.
        Also assign a priority: 'low', 'medium', 'high', 'critical'.
        
        Description: "{description}"
        
        Respond ONLY with a valid JSON object in this format:
        {{
            "suggested_category": "...",
            "suggested_priority": "..."
        }}
        """

        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        return json.loads(response.text)

    except Exception as e:
        print(f"LLM Classification Error: {e}")
        return {
            "suggested_category": "general", 
            "suggested_priority": "medium", 
            "error": str(e) or "Unknown error"
        }

def suggest_reply_draft(description, past_comments_text):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": "Missing API Key"}

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash") 

        prompt = f"""
        You are an expert IT routing agent for NexusDesk.
        A customer reported this issue: "{description}".
        
        Here is how we solved similar issues in the past:
        {past_comments_text}
        
        Based on the issue and the conversation history, generate a polite response for the customer.
        Additionally, determine the new status of the ticket. If you are providing a final solution, the status should be "resolved". If you are asking a clarifying question, it should be "open" or "in_progress".
        
        Respond ONLY with a valid JSON object in this format:
        {{
            "suggestion": "...",
            "suggested_status": "open|in_progress|resolved|closed"
        }}
        """

        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"LLM Reply Error: {e}")
        return {"error": str(e) or "Unknown error"}

