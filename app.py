# app.py
from flask import Flask, render_template, request, Response, session
from flask_cors import CORS
import requests
import json

app = Flask(__name__, static_url_path='/static')
CORS(app)
app.secret_key = 'secret'

OLLAMA_URL = "http://localhost:10001/api/generate"
MODEL = "gemma3:1b"

@app.route('/')
def index():
    return render_template('layout.html')

@app.route('/api/chat/stream', methods=['GET'])
def chat_stream():
    prompt = request.args.get("prompt", "")
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": True
    }

    def generate():
        buffer = ''
        with requests.post(OLLAMA_URL, json=payload, stream=True) as res:
            for line in res.iter_lines():
                if line:
                    try:
                        obj = json.loads(line)
                        token = obj.get("response", "")
                        buffer += token
                        yield f"data: {token}\n\n"
                    except:
                        continue
        session.setdefault("history", []).append({"prompt": prompt, "response": buffer})
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/chat/history')
def chat_history():
    return session.get("history", [])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
