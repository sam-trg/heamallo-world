# app.py
from flask import Flask, render_template, request, Response, session
from flask_cors import CORS
import requests
import json
import re
from html import escape

app = Flask(__name__, static_url_path='/static')
CORS(app)
app.secret_key = 'secret'

OLLAMA_URL = "http://localhost:10001/api/generate"
MODEL = "gemma3:1b"
MAX_HISTORY_MESSAGES = 10  # Limit the context window to last 10 messages
MAX_PROMPT_LENGTH = 2000  # Maximum length for user input
MIN_PROMPT_LENGTH = 1     # Minimum length for user input

SYSTEM_PROMPT = """You are a helpful AI assistant. Be friendly and conversational, but keep your responses concise and to the point. Don't use markdown formatting."""

def sanitize_input(text):
    """Sanitize user input by removing control characters and unwanted patterns."""
    if not isinstance(text, str):
        return ""
        
    # Remove control characters except newlines and tabs
    text = ''.join(char for char in text if char == '\n' or char == '\t' or (ord(char) >= 32 and ord(char) != 127))
    
    # Convert multiple newlines to max of 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Convert multiple spaces/tabs to single space
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Trim leading/trailing whitespace
    return text.strip()

def validate_prompt(prompt):
    """Validate the prompt and return (is_valid, error_message)."""
    if not prompt:
        return False, "Empty prompt"
        
    if len(prompt) > MAX_PROMPT_LENGTH:
        return False, f"Prompt too long (max {MAX_PROMPT_LENGTH} characters)"
        
    if len(prompt) < MIN_PROMPT_LENGTH:
        return False, "Prompt too short"
    
    # Check for minimum meaningful content (not just whitespace/special chars)
    meaningful_content = re.sub(r'[\s\W]+', '', prompt)
    if not meaningful_content:
        return False, "Prompt must contain meaningful content"
    
    return True, None

def format_conversation_context(history, current_prompt):
    """Format the conversation history and current prompt into a context string."""
    # Start with system prompt
    context = f"System: {SYSTEM_PROMPT}\n\n"
    
    # Take only the last MAX_HISTORY_MESSAGES
    recent_history = history[-MAX_HISTORY_MESSAGES:] if history else []
    
    try:
        # Add conversation history
        for msg in recent_history:
            # Sanitize historical messages as well
            safe_prompt = sanitize_input(msg['prompt'])
            safe_response = sanitize_input(msg['response'])
            context += f"Human: {safe_prompt}\n"
            context += f"Assistant: {safe_response}\n\n"
        
        # Add current prompt (already sanitized)
        context += f"Human: {current_prompt}\n"
        context += "Assistant: "
        return context
    except Exception as e:
        app.logger.error(f"Error formatting context: {str(e)}")
        return f"System: {SYSTEM_PROMPT}\n\nHuman: {current_prompt}\nAssistant: "

@app.route('/')
def index():
    return render_template('layout.html')

@app.route('/api/chat/stream', methods=['GET'])
def chat_stream():
    try:
        raw_prompt = request.args.get("prompt", "")
        
        # Sanitize input
        prompt = sanitize_input(raw_prompt)
        
        # Validate prompt
        is_valid, error_message = validate_prompt(prompt)
        if not is_valid:
            return Response(f"data: {json.dumps({'error': error_message})}\n\n", 
                          mimetype='text/event-stream')
        
        history = session.get("history", [])
        context = format_conversation_context(history, prompt)
        
        payload = {
            "model": MODEL,
            "prompt": context,
            "stream": True
        }

        def generate():
            buffer = ''
            try:
                with requests.post(OLLAMA_URL, json=payload, stream=True) as res:
                    if res.status_code != 200:
                        yield f"data: {json.dumps({'error': f'Ollama API error: {res.status_code}'})}\n\n"
                        return
                        
                    for line in res.iter_lines():
                        if line:
                            try:
                                obj = json.loads(line)
                                token = obj.get("response", "")
                                buffer += token
                                yield f"data: {token}\n\n"
                            except json.JSONDecodeError:
                                continue
                # Send the final [DONE] message with the complete response
                yield f"data: {json.dumps({'done': True, 'fullResponse': buffer})}\n\n"
            except requests.RequestException as e:
                yield f"data: {json.dumps({'error': f'Connection error: {str(e)}'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'Unexpected error: {str(e)}'})}\n\n"

        return Response(generate(), mimetype='text/event-stream')
    except Exception as e:
        return Response(f"data: {json.dumps({'error': f'Server error: {str(e)}'})}\n\n", 
                       mimetype='text/event-stream')

@app.route('/api/chat/history')
def chat_history():
    return session.get("history", [])

@app.route('/api/chat/reset', methods=['POST'])
def reset_chat():
    session["history"] = []
    return {"status": "success"}

@app.route('/api/chat/save', methods=['POST'])
def save_chat():
    try:
        data = request.json
        if not data or 'prompt' not in data or 'response' not in data:
            return {"status": "error", "message": "Missing prompt or response"}, 400
            
        # Sanitize inputs
        safe_prompt = sanitize_input(data["prompt"])
        safe_response = sanitize_input(data["response"])
        
        # Validate prompt
        is_valid, error_message = validate_prompt(safe_prompt)
        if not is_valid:
            return {"status": "error", "message": error_message}, 400
        
        # Ensure we don't exceed a reasonable session size
        history = session.get("history", [])
        if len(history) >= 100:  # Limit total history size
            history = history[-90:]  # Keep last 90 messages when limit is reached
        
        history.append({
            "prompt": safe_prompt,
            "response": safe_response
        })
        session["history"] = history
        return {"status": "success"}
    except Exception as e:
        app.logger.error(f"Error saving chat: {str(e)}")
        return {"status": "error", "message": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
