import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Percorso per il database JSON
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')

# --- CONFIGURAZIONE CHIAVE AI (CON PULIZIA AUTOMATICA) ---
raw_key = os.environ.get("GEMINI_API_KEY", "")
# Questa riga pulisce la chiave da virgolette doppie, singole e spazi bianchi
API_KEY = raw_key.replace('"', '').replace("'", "").strip()

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        print("SISTEMA: Gemini configurato correttamente.")
    except Exception as e:
        print(f"ERRORE CONFIGURAZIONE AI: {str(e)}")

# --- ROTTE DEL SERVER ---

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify({"ok": True, "state": data})
        except:
            return jsonify({"ok": False, "error": "Errore lettura file"})
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

# Rotta 1: Analisi Ordini (Risponde in JSON puro per il catalogo)
@app.route('/api/ai/parse', methods=['POST'])
def parse_order():
    try:
        if not API_KEY:
            raise ValueError("Chiave GEMINI_API_KEY non trovata nelle variabili Railway.")
        
        req_data = request.json
        text = req_data.get('text', '')
        catalog = req_data.get('catalog', [])
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Sei l'assistente acquisti di Sea Signora Milano. Leggi questo ordine: "{text}". 
        Trova i prodotti in questo catalogo: {json.dumps(catalog)}. 
        RISPONDI SOLO CON UN ARRAY JSON VALIDO: [{{"id": <id_prodotto>, "qty": <quantità>}}]
        Nessun backtick, nessun markdown, nessuna parola extra. Solo il JSON.
        """
        
        response = model.generate_content(prompt)
        # Pulizia della risposta da eventuali blocchi di codice markdown
        clean_response = response.text.replace('```json', '').replace('```', '').strip()
        
        return jsonify({"ok": True, "parsed": {"items": json.loads(clean_response)}})
    except Exception as e:
        print(f"ERRORE AI PARSE: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

# Rotta 2: Chat Assistente (Risponde in testo normale per l'utente)
@app.route('/api/ai/help', methods=['POST'])
def ai_help():
    try:
        if not API_KEY:
            raise ValueError("Chiave GEMINI_API_KEY non trovata nelle variabili Railway.")
        
        req_data = request.json
        question = req_data.get('question', '')
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Sei l'assistente virtuale del sistema Sea Signora Milano. 
        Rispondi in italiano in modo breve e cordiale a questa domanda: "{question}".
        Spiega all'utente come usare l'app se necessario (es: caricare listini da Configurazione).
        Non usare formattazione complessa.
        """
        
        response = model.generate_content(prompt)
        return jsonify({"ok": True, "answer": response.text.strip()})
    except Exception as e:
        print(f"ERRORE AI HELP: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

# Avvio applicazione
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# Gunicorn esporta l'oggetto "application"
application = app
