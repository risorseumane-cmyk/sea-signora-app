import json
import os
import sqlite3
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import google.generativeai as genai


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app_data.db"
FRONTEND_FILE = BASE_DIR.parent / "index.html"
ASSETS_DIR = BASE_DIR.parent / "assets"
API_KEY = os.getenv("SEASIGNORA_API_KEY", "cambia-questa-chiave")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@seasignorarest.com")
SMTP_TO = os.getenv("SMTP_TO", "Amministrazione@seasignorarest.com")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", SMTP_FROM)
FORMSPREE_ENDPOINT = os.getenv("FORMSPREE_ENDPOINT", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAM9BA5AvXsyu2RWWJSLh_xQ55isa2sp94").strip()

# Configurazione Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
CORS(app)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            delivered INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    default_state = {
        "products": [
            {"id":1, "name":"Tartufi di Mare", "cat":"Ittico", "um":"kg", "prices":{"METRO":11.12}},
            {"id":2, "name":"Astice Blu Vivo", "cat":"Ittico", "um":"kg", "prices":{"OROBICA":65.90}},
            {"id":3, "name":"Gambero Rosso 2°", "cat":"Ittico", "um":"kg", "prices":{"OROBICA":59.00}},
            {"id":4, "name":"Branzino Grecia", "cat":"Ittico", "um":"kg", "prices":{"METRO":11.71}},
            {"id":5, "name":"Carciofi Mammola", "cat":"Verdure", "um":"pz", "prices":{"OROBICA":1.18}},
            {"id":6, "name":"Patate", "cat":"Verdure", "um":"kg", "prices":{"ORTOLANO":0.90}},
            {"id":7, "name":"Carne Trita 80/20", "cat":"Carne", "um":"kg", "prices":{"CARNI NOBILI":10.00}},
            {"id":8, "name":"Pasta Staff", "cat":"Secchi", "um":"kg", "prices":{"METRO":1.16}},
            {"id":11, "name":"Ostriche Gillardeau", "cat":"Ittico", "um":"pz", "prices":{"LINEA MARE":2.44}},
            {"id":12, "name":"Tonno Rosso Fuentes", "cat":"Ittico", "um":"kg", "prices":{"OROBICA":29.00}}
        ],
        "suppliers": [
            {"name":"METRO", "min":150, "current": 0},
            {"name":"OROBICA", "min":250, "current": 0},
            {"name":"LINEA MARE", "min":200, "current": 0},
            {"name":"REACH FOOD", "min":300, "current": 0},
            {"name":"MARR", "min":200, "current": 0},
            {"name":"ORTOLANO", "min":100, "current": 0}
        ],
        "reparti": ["Cucina", "Sala", "Bar", "Wine"],
        "inbox": [],
        "archive": [],
        "settings": {
            "brandName": "Sea Signora",
            "accentColor": "#c5a059",
            "aiEnabled": True
        },
    }
    cur.execute("SELECT id FROM app_state WHERE id = 1")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO app_state (id, state_json, updated_at) VALUES (1, ?, ?)",
            (json.dumps(default_state), datetime.utcnow().isoformat()),
        )
    conn.commit()
    conn.close()


def check_key():
    # Authentication disabled by request: keep APIs open without password.
    return True


def sanitize_state(state):
    if not isinstance(state, dict):
        return {}
    safe = dict(state)
    settings = dict(safe.get("settings") or {})
    settings.pop("serverApiKey", None)
    settings.pop("aiApiKey", None)
    settings.pop("serverUrl", None)
    safe["settings"] = settings
    return safe


def _recipient_list():
    return [addr.strip() for addr in SMTP_TO.split(",") if addr.strip()]


def send_email_smtp(subject, body):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        return False, "SMTP non configurato"
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    recipients = _recipient_list() or [SMTP_TO]
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(recipients)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, recipients, msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)


def send_email_resend(subject, body):
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY non configurata"
    recipients = _recipient_list()
    if not recipients:
        return False, "SMTP_TO non configurato"

    payload = {
        "from": RESEND_FROM,
        "to": recipients,
        "subject": subject,
        "text": body,
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if 200 <= response.status < 300:
                return True, ""
            return False, f"Resend status {response.status}"
    except urllib.error.HTTPError as e:
        details = ""
        try:
            details = e.read().decode("utf-8")
        except Exception:
            details = str(e)
        return False, f"Resend HTTP {e.code}: {details[:300]}"
    except Exception as e:
        return False, f"Resend error: {str(e)}"


def send_email_formspree(subject, body):
    if not FORMSPREE_ENDPOINT:
        return False, "FORMSPREE_ENDPOINT non configurato"
    payload = {
        "subject": subject,
        "message": body,
        "to": SMTP_TO,
        "from": SMTP_FROM,
        "_subject": subject,
    }
    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        FORMSPREE_ENDPOINT,
        data=encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            # Formspree/Cloudflare may block default python-urllib signature.
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Origin": "https://seasignora-ordini.up.railway.app",
            "Referer": "https://seasignora-ordini.up.railway.app/",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if 200 <= response.status < 300:
                return True, ""
            return False, f"Formspree status {response.status}"
    except urllib.error.HTTPError as e:
        details = ""
        try:
            details = e.read().decode("utf-8")
        except Exception:
            details = str(e)
        return False, f"Formspree HTTP {e.code}: {details[:300]}"
    except Exception as e:
        return False, f"Formspree error: {str(e)}"


def send_email(subject, body):
    ok, err = send_email_formspree(subject, body)
    if ok:
        return True, "formspree"
    resend_ok, resend_err = send_email_resend(subject, body)
    if resend_ok:
        return True, "resend"
    smtp_ok, smtp_err = send_email_smtp(subject, body)
    if smtp_ok:
        return True, "smtp"
    return False, f"Formspree: {err} | Resend: {resend_err} | SMTP: {smtp_err}"

def log_notification(kind, subject, body, delivered, error_text=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO notification_log (kind, subject, body, delivered, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            kind,
            subject,
            body,
            1 if delivered else 0,
            (error_text or "")[:1000],
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


init_db()


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "time": datetime.utcnow().isoformat()})


@app.get("/api/state")
def get_state():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state_json, updated_at FROM app_state WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"ok": False, "error": "State not found"}), 404
    state = sanitize_state(json.loads(row["state_json"]))
    return jsonify({"ok": True, "state": state, "updatedAt": row["updated_at"]})


@app.post("/api/state")
def save_state():
    if not check_key():
        return jsonify({"ok": False, "error": "Invalid API key"}), 401

    payload = request.get_json(silent=True) or {}
    state = payload.get("state")
    if not isinstance(state, dict):
        return jsonify({"ok": False, "error": "Invalid state payload"}), 400
    state = sanitize_state(state)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE app_state SET state_json = ?, updated_at = ? WHERE id = 1",
        (json.dumps(state), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.post("/api/order")
def create_order():
    if not check_key():
        return jsonify({"ok": False, "error": "Invalid API key"}), 401

    payload = request.get_json(silent=True) or {}
    dept = str(payload.get("dept") or "").strip()
    staff = str(payload.get("staff") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not staff or not text:
        return jsonify({"ok": False, "error": "Missing required fields"}), 400
    if not dept:
        dept = "Reparto"

    now_iso = datetime.utcnow().isoformat()
    req_id = int(datetime.utcnow().timestamp() * 1000)
    req_item = {
        "id": req_id,
        "staff": staff,
        "dept": dept,
        "createdAt": now_iso,
        "date": datetime.utcnow().strftime("%H:%M:%S"),
        "text": text,
    }

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state_json FROM app_state WHERE id = 1")
    row = cur.fetchone()
    state = json.loads(row["state_json"]) if row and row["state_json"] else {}
    if not isinstance(state, dict):
        state = {}
    inbox = state.get("inbox")
    if not isinstance(inbox, list):
        inbox = []
    order_history = state.get("orderHistory")
    if not isinstance(order_history, list):
        order_history = []

    inbox.append(req_item)
    order_history.insert(
        0,
        {
            **req_item,
            "status": "in_attesa",
            "updatedAt": now_iso,
        },
    )
    state["inbox"] = inbox
    state["orderHistory"] = order_history

    cur.execute(
        "UPDATE app_state SET state_json = ?, updated_at = ? WHERE id = 1",
        (json.dumps(state), now_iso),
    )
    conn.commit()
    conn.close()

    subject = "[Sea Signora] Nuovo ordine reparto"
    body = (
        f"Nuovo ordine ricevuto\n\n"
        f"Reparto: {dept}\n"
        f"Operatore: {staff}\n"
        f"Testo: {text}\n"
        f"Data: {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC\n"
    )
    ok, err = send_email(subject, body)
    log_notification("order", subject, body, ok, err)

    return jsonify(
        {
            "ok": True,
            "id": req_id,
            "emailDelivered": bool(ok),
            "emailError": "" if ok else (err or "Email delivery failed"),
        }
    )


@app.post("/api/notify")
def notify():
    if not check_key():
        return jsonify({"ok": False, "error": "Invalid API key"}), 401
    payload = request.get_json(silent=True) or {}
    kind = payload.get("type", "generic")
    data = payload.get("data", {})

    if kind == "order":
        subject = "[Sea Signora] Nuovo ordine reparto"
        body = (
            f"Nuovo ordine ricevuto\n\n"
            f"Reparto: {data.get('dept', '-')}\n"
            f"Operatore: {data.get('staff', '-')}\n"
            f"Testo: {data.get('text', '-')}\n"
            f"Data: {data.get('date', '-')}\n"
        )
    elif kind == "price_alert":
        subject = "[Sea Signora] Alert aumento prezzi"
        body = (
            f"Sono stati rilevati aumenti prezzo > soglia.\n\n"
            f"Dettagli:\n{data.get('message', '-')}\n"
        )
    else:
        subject = "[Sea Signora] Notifica"
        body = json.dumps(data, ensure_ascii=False, indent=2)

    ok, err = send_email(subject, body)
    log_notification(kind, subject, body, ok, err)
    if not ok:
        return jsonify(
            {
                "ok": True,
                "delivered": False,
                "queued": True,
                "warning": f"Email non inviata: {err}",
                "debug": {
                    "formspreeConfigured": bool(FORMSPREE_ENDPOINT),
                    "resendConfigured": bool(RESEND_API_KEY),
                    "host": SMTP_HOST,
                    "port": SMTP_PORT,
                    "user": SMTP_USER,
                    "to": SMTP_TO,
                },
            }
        )
    return jsonify({"ok": True, "delivered": True})


def get_gemini_response(prompt, model_name="gemini-1.5-flash"):
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Errore Gemini ({model_name}): {e}")
        return None


@app.post("/api/ai/order-parse")
def ai_order_parse():
    if not check_key():
        return jsonify({"ok": False, "error": "Invalid API key"}), 401

    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "GEMINI_API_KEY non configurata"}), 503

    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text") or "").strip()
    catalog = payload.get("catalog") or []

    if not text:
        return jsonify({"ok": False, "error": "Testo mancante"}), 400

    prompt = (
        "Sei l'assistente smart di Sea Signora.\n"
        "Analizza questa richiesta di ordine e associala ai prodotti del catalogo.\n"
        "Restituisci SOLO un JSON con questo formato: {\"items\": [{\"productId\": ID, \"qty\": NUMERO, \"name\": \"NOME\"}]}\n"
        f"CATALOGO:\n{json.dumps(catalog, ensure_ascii=False)}\n\n"
        f"ORDINE:\n{text}"
    )

    response_text = get_gemini_response(prompt)
    if not response_text:
        return jsonify({"ok": False, "error": "Errore AI"}), 502

    try:
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start >= 0 and end > start:
            response_text = response_text[start : end + 1]
        parsed = json.loads(response_text)
        return jsonify({"ok": True, "parsed": parsed})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Errore parsing AI: {str(e)}"}), 502


@app.post("/api/ai/help")
def ai_help():
    if not check_key():
        return jsonify({"ok": False, "error": "Invalid API key"}), 401

    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "GEMINI_API_KEY non configurata"}), 503

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question") or "").strip()
    context = payload.get("context") or {}

    if not question:
        return jsonify({"ok": False, "error": "Domanda mancante"}), 400

    prompt = (
        "Sei l'assistente smart di Sea Signora.\n"
        "Rispondi in modo professionale e utile in italiano.\n"
        f"CONTESTO: {json.dumps(context, ensure_ascii=False)}\n"
        f"DOMANDA: {question}"
    )

    response_text = get_gemini_response(prompt)
    if response_text:
        return jsonify({"ok": True, "answer": response_text.strip()})
    
    return jsonify({"ok": False, "error": "Impossibile ottenere risposta dall'IA"}), 502


@app.get("/api/notifications")
def get_notifications():
    if not check_key():
        return jsonify({"ok": False, "error": "Invalid API key"}), 401
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, kind, subject, delivered, error, created_at
        FROM notification_log
        ORDER BY id DESC
        LIMIT 200
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"ok": True, "items": rows})


@app.get("/")
def home():
    if FRONTEND_FILE.exists():
        return send_from_directory(FRONTEND_FILE.parent, FRONTEND_FILE.name)
    return jsonify({"ok": False, "error": "Frontend not found"}), 404


@app.get("/assets/<path:filename>")
def assets(filename):
    if ASSETS_DIR.exists():
        return send_from_directory(ASSETS_DIR, filename)
    return jsonify({"ok": False, "error": "Assets not found"}), 404


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug_mode)
