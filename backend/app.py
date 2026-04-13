import json
import os
import sqlite3
import smtplib
import urllib.error
import urllib.parse
import urllib.request
import difflib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# --- CONFIGURAZIONE ---
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app_data.db"
FRONTEND_FILE = BASE_DIR.parent / "index.html"

# Chiavi e Configurazione (GEMINI RIMOSSO - Motore Locale Attivo)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@seasignorarest.com")
SMTP_TO = os.getenv("SMTP_TO", "Amministrazione@seasignorarest.com")
FORMSPREE_ENDPOINT = os.getenv("FORMSPREE_ENDPOINT", "")

app = Flask(__name__)
CORS(app)

# --- DATABASE ---
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS app_state (id INTEGER PRIMARY KEY, state TEXT)")
        # Inizializza con stato di default se vuoto
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM app_state")
        if cur.fetchone()[0] == 0:
            default_state = {
                "settings": {"brandName": "Sea Signora", "color": "#c5a059", "homeTitle": "Corporate Home"},
                "products": [
                    {"id": 1, "name": "Aragosta Viva", "cat": "Ittico", "prices": {"METRO": 45.00, "Ittica": 42.50}},
                    {"id": 2, "name": "Gin Tonic Premium", "cat": "Spirits", "prices": {"Beverage": 12.00, "METRO": 13.50}},
                    {"id": 3, "name": "Pane Brioche", "cat": "Forno", "prices": {"Fornaio": 2.50, "METRO": 3.00}}
                ],
                "suppliers": [
                    {"name": "METRO", "min": 250, "current": 0},
                    {"name": "Ittica", "min": 150, "current": 0},
                    {"name": "Beverage", "min": 300, "current": 0},
                    {"name": "Fornaio", "min": 50, "current": 0}
                ],
                "reparti": ["Cucina", "Sala", "Bar", "Wine"],
                "inbox": [],
                "archive": []
            }
            conn.execute("INSERT INTO app_state (id, state) VALUES (1, ?)", (json.dumps(default_state),))
            conn.commit()

init_db()

# --- UTILITIES ---
def send_email_alert(dept, staff, text):
    subject = f"NUOVO ORDINE: {dept} da {staff}"
    body = f"Reparto: {dept}\nStaff: {staff}\nData: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\nOrdine:\n{text}"
    
    # SMTP
    if SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = SMTP_FROM
            msg['To'] = SMTP_TO
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"SMTP Error: {e}")
            
    # Formspree Fallback
    if FORMSPREE_ENDPOINT:
        try:
            data = urllib.parse.urlencode({"_subject": subject, "message": body}).encode()
            urllib.request.urlopen(FORMSPREE_ENDPOINT, data=data)
            return True
        except Exception as e:
            print(f"Formspree Error: {e}")
            
    return False

def local_smart_parse(text, products):
    """Motore di parsing locale 'Smart Matcher' (senza chiavi API)."""
    items = []
    lines = text.split('\n')
    product_names = [p['name'] for p in products]
    
    # Parole comuni da ignorare nel match del nome
    stop_words = {'di', 'da', 'il', 'la', 'un', 'una', 'con', 'per', 'kg', 'casse', 'cassa', 'pz', 'pezzi', 'lt', 'litri'}

    for line in lines:
        line = line.strip().lower()
        if not line: continue
        
        # Estrazione Quantità avanzata
        qty = 1.0
        words = line.split()
        
        # Cerca il primo numero nella riga
        for i, word in enumerate(words):
            clean_word = word.replace(',', '.', 1)
            # Gestisce formati come "5kg" o "10pz"
            num_part = ""
            for char in clean_word:
                if char.isdigit() or char == '.':
                    num_part += char
                else:
                    break
            
            if num_part and num_part.replace('.', '', 1).isdigit():
                qty = float(num_part)
                # Rimuovi la parola che conteneva il numero per non sporcare il match del nome
                words.pop(i)
                break
        
        # Pulisci la riga dai termini di unità di misura rimasti
        clean_words = [w for w in words if w not in stop_words]
        clean_line = " ".join(clean_words)
        
        if not clean_line: continue

        # Match fuzzy sul nome prodotto
        matches = difflib.get_close_matches(clean_line, [n.lower() for n in product_names], n=1, cutoff=0.25)
        if matches:
            match_name = matches[0]
            p_orig = next(p for p in products if p['name'].lower() == match_name)
            items.append({
                "productId": p_orig['id'],
                "name": p_orig['name'],
                "qty": qty,
                "cat": p_orig['cat']
            })
    return {"items": items}

# --- API ROUTES ---
@app.get("/api/state")
def get_state():
    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        if row:
            return jsonify({"ok": True, "state": json.loads(row['state'])})
    return jsonify({"ok": False, "error": "No state found"}), 404

@app.post("/api/state")
def post_state():
    data = request.get_json()
    if not data or 'state' not in data:
        return jsonify({"ok": False, "error": "Invalid state"}), 400
    with get_conn() as conn:
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(data['state']),))
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/order")
def create_order():
    data = request.get_json()
    dept = data.get("dept")
    staff = data.get("staff")
    text = data.get("text")
    
    if not dept or not staff or not text:
        return jsonify({"ok": False, "error": "Missing fields"}), 400
        
    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        state = json.loads(row['state'])
        
        new_req = {
            "id": int(datetime.now().timestamp()),
            "dept": dept,
            "staff": staff,
            "text": text,
            "date": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        state["inbox"].insert(0, new_req)
        
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.commit()
        
    # Notifica via mail
    sent = send_email_alert(dept, staff, text)
    
    return jsonify({"ok": True, "notified": sent})

@app.post("/api/ai/order-parse")
def ai_parse():
    p = request.get_json()
    try:
        parsed = local_smart_parse(p.get('text', ''), p.get('catalog', []))
        return jsonify({"ok": True, "parsed": parsed})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/ai/help")
def ai_help():
    data = request.get_json()
    q = data.get("question", "").lower()
    if "prezzo" in q or "cost" in q: 
        ans = "I prezzi migliori sono evidenziati nel Master Data e nella Heatmap Comparazione. Puoi aggiornare i prezzi nella sezione 'Aggiorna Fatture'."
    elif "ordine" in q or "reparto" in q: 
        ans = "Puoi gestire gli ordini in arrivo nella sezione Inbox. I reparti ordinano tramite QR code dedicato."
    elif "heatmap" in q:
        ans = "La Heatmap mostra l'intensità di spesa incrociando reparti, categorie e fornitori. Si aggiorna automaticamente con ogni ordine approvato."
    elif "trend" in q or "grafic" in q:
        ans = "I grafici di trend mostrano l'andamento della spesa su base settimanale, mensile o trimestrale."
    else: 
        ans = "Sono l'assistente locale di Sea Signora. Posso aiutarti a gestire il catalogo, monitorare gli ordini e analizzare le spese dei fornitori."
    return jsonify({"ok": True, "answer": ans})

@app.get("/api/diag")
def diagnostics():
    diag = {"db": "unknown", "engine": "Local Smart Matcher (OK)"}
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM app_state")
            diag["db"] = f"OK (rows: {cur.fetchone()[0]})"
    except Exception as e:
        diag["db"] = f"Error: {str(e)}"
    return jsonify(diag)

@app.post("/api/admin/reset-db")
def reset_db():
    with get_conn() as conn:
        conn.execute("DELETE FROM app_state")
        conn.commit()
    init_db()
    return jsonify({"ok": True})

@app.post("/api/admin/page-settings")
def update_settings():
    data = request.get_json()
    settings = data.get("settings")
    if not settings: return jsonify({"ok": False, "error": "Missing settings"}), 400
    
    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        state = json.loads(row['state'])
        state["settings"] = settings
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/admin/suppliers")
def update_suppliers():
    data = request.get_json()
    suppliers = data.get("suppliers")
    if not suppliers: return jsonify({"ok": False, "error": "Missing suppliers"}), 400
    
    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        state = json.loads(row['state'])
        state["suppliers"] = suppliers
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.commit()
    return jsonify({"ok": True})

# --- SERVING FRONTEND ---
@app.route("/")
def index():
    return send_from_directory(FRONTEND_FILE.parent, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
