import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# File dove il server salverà ordini e prodotti
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')

# Configura l'Intelligenza Artificiale di Google
API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# Questa rotta serve la tua interfaccia grafica (index.html)
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# Rotta per inviare i dati all'app
@app.route('/api/state', methods=['GET'])
def get_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({"ok": True, "state": data})
    else:
        return jsonify({"ok": False, "error": "Nessun dato presente"})

# Rotta per salvare i dati che arrivano dall'app
@app.route('/api/state', methods=['POST'])
def save_state():
    try:
        data = request.json.get('state', {})
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Rotta dove lavora Gemini (legge l'ordine e cerca nel catalogo)
@app.route('/api/ai/parse', methods=['POST'])
def parse_order():
    try:
        if not API_KEY:
            raise ValueError("Chiave GEMINI_API_KEY non configurata su Railway.")
        
        req_data = request.json
        text = req_data.get('text', '')
        catalog = req_data.get('catalog', [])
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Sei l'assistente acquisti di Sea Signora Milano. 
        Leggi questo ordine: "{text}". 
        Trova i prodotti in questo catalogo: {json.dumps(catalog)}. 
        RISPONDI SOLO CON UN ARRAY JSON VALIDO: [{{"id": <id_prodotto>, "qty": <quantità>}}]
        Nessun backtick, nessun testo aggiuntivo, solo il JSON puro.
        """
        
        response = model.generate_content(prompt)
        response_text = response.text.replace('```json', '').replace('```', '').strip()
        
        return jsonify({"ok": True, "parsed": {"items": json.loads(response_text)}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Entry point per Railway
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# Gunicorn ha bisogno di chiamare l'app "application"
application = app
