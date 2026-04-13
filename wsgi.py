import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({"ok": True, "state": data})
    else:
        return jsonify({"ok": False, "error": "Nessun dato presente"})

@app.route('/api/state', methods=['POST'])
def save_state():
    try:
        data = request.json.get('state', {})
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Rotta 1: Analisi Ordini (Risponde in JSON)
@app.route('/api/ai/parse', methods=['POST'])
def parse_order():
    try:
        if not API_KEY:
            raise ValueError("Chiave GEMINI API KEY mancante su Railway.")
        
        req_data = request.json
        text = req_data.get('text', '')
        catalog = req_data.get('catalog', [])
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Sei l'assistente acquisti di Sea Signora Milano. Leggi questo ordine: "{text}". 
        Trova i prodotti in questo catalogo: {json.dumps(catalog)}. 
        RISPONDI SOLO CON UN ARRAY JSON VALIDO: [{{"id": <id_prodotto>, "qty": <quantità>}}]
        Nessun backtick, nessun testo aggiuntivo, solo il JSON puro.
        """
        
        response = model.generate_content(prompt)
        response_text = response.text.replace('```json', '').replace('```', '').strip()
        return jsonify({"ok": True, "parsed": {"items": json.loads(response_text)}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Rotta 2: Chat di Aiuto Libera (Risponde in testo normale)
@app.route('/api/ai/help', methods=['POST'])
def ai_help():
    try:
        if not API_KEY:
            raise ValueError("Chiave GEMINI API KEY mancante su Railway.")
        
        req_data = request.json
        question = req_data.get('question', '')
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Sei l'assistente virtuale dell'applicazione 'PriceTag Smartmind' per il ristorante Sea Signora Milano.
        Rispondi in italiano, in modo conciso, professionale e utile a questa domanda dell'utente: "{question}".
        Informazioni di sistema utili:
        - Per importare il catalogo: usare la tab Configurazione -> Prodotti & Excel.
        - Per fare un ordine: usare i QR code dei reparti.
        Non usare formattazioni complesse come il Markdown.
        """
        
        response = model.generate_content(prompt)
        return jsonify({"ok": True, "answer": response.text.strip()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

application = app
