import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')

# --- CONFIGURAZIONE CHIAVE E PULIZIA ---
raw_key = os.environ.get("GEMINI_API_KEY", "")
API_KEY = raw_key.replace('"', '').replace("'", "").strip()

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        print("SISTEMA: Configurazione API completata.")
    except Exception as e:
        print(f"ERRORE CONFIGURAZIONE: {str(e)}")

# --- ROTTE ---
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return jsonify({"ok": True, "state": json.load(f)})
    return jsonify({"ok": False, "error": "Nessun dato"})

@app.route('/api/state', methods=['POST'])
def save_state():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(request.json.get('state', {}), f, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Rotta 1: Analisi Ordini
@app.route('/api/ai/parse', methods=['POST'])
def parse_order():
    try:
        req_data = request.json
        text = req_data.get('text', '')
        catalog = req_data.get('catalog', [])
        
        # Usiamo il modello specifico corretto per le versioni recenti dell'SDK
        model = genai.GenerativeModel(model_name='gemini-1.5-flash')
        
        prompt = f"Sei l'assistente acquisti di Sea Signora Milano. Leggi: '{text}'. Catalogo: {json.dumps(catalog)}. RISPONDI SOLO JSON: [{{\"id\": <id>, \"qty\": <quantità>}}]"
        
        response = model.generate_content(prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return jsonify({"ok": True, "parsed": {"items": json.loads(clean_text)}})
    except Exception as e:
        print(f"ERRORE AI PARSE: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

# Rotta 2: Chat Aiuto
@app.route('/api/ai/help', methods=['POST'])
def ai_help():
    try:
        question = request.json.get('question', '')
        # Cambio tattico: se 1.5-flash dà ancora 404, prova gemini-1.5-flash-latest o gemini-pro
        model = genai.GenerativeModel(model_name='gemini-1.5-flash')
        
        prompt = f"Rispondi come assistente virtuale del ristorante Sea Signora Milano in modo breve a: '{question}'"
        
        response = model.generate_content(prompt)
        return jsonify({"ok": True, "answer": response.text.strip()})
    except Exception as e:
        print(f"ERRORE AI HELP: {str(e)}")
        # Messaggio di fallback più utile se Google continua a dare 404
        if "404" in str(e):
            return jsonify({"ok": True, "answer": "L'IA è in manutenzione, ma il sistema è attivo. Puoi usare l'app manualmente!"})
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

application = app
