import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
raw_key = os.environ.get("GEMINI_API_KEY", "")
API_KEY = raw_key.replace('"', '').replace("'", "").strip()

if API_KEY:
    genai.configure(api_key=API_KEY)

def get_gemini_response(prompt, is_json=False):
    # Prova i modelli in ordine di disponibilità
    models_to_try = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Modello {model_name} fallito: {str(e)}")
            continue
    raise Exception("Nessun modello Gemini disponibile.")

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/state', methods=['GET', 'POST'])
def handle_state():
    if request.method == 'GET':
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return jsonify({"ok": True, "state": json.load(f)})
        return jsonify({"ok": False})
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(request.json.get('state', {}), f, indent=2)
    return jsonify({"ok": True})

@app.route('/api/ai/parse', methods=['POST'])
def parse_order():
    try:
        d = request.json
        prompt = f"Sei l'assistente di Sea Signora Milano. Estrai JSON da: '{d['text']}'. Catalogo: {json.dumps(d['catalog'])}. Rispondi SOLO con JSON: [{{'id': <id>, 'qty': <qty>}}]"
        res = get_gemini_response(prompt)
        clean = res.replace('```json', '').replace('```', '').strip()
        return jsonify({"ok": True, "parsed": {"items": json.loads(clean)}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/ai/help', methods=['POST'])
def ai_help():
    try:
        q = request.json.get('question', '')
        prompt = f"Rispondi come assistente virtuale esperto per il ristorante Sea Signora Milano a: '{q}'"
        res = get_gemini_response(prompt)
        return jsonify({"ok": True, "answer": res.strip()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

application = app
