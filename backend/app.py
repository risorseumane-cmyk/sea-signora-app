import json
import os
import sqlite3
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app_data.db"
FRONTEND_FILE = BASE_DIR.parent / "index.html"
API_KEY = os.getenv("SEASIGNORA_API_KEY", "cambia-questa-chiave")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@seasignorarest.com")
SMTP_TO = os.getenv("SMTP_TO", "Amministrazione@seasignorarest.com")

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
        "products": [],
        "suppliers": [],
        "reparti": ["Cucina", "Sala", "Bar", "Wine"],
        "inbox": [],
        "archive": [],
        "priceHistory": [],
        "settings": {
            "brandName": "Sea Signora",
            "accentColor": "#c5a059",
            "hiddenModules": {},
            "allocationMode": "hybrid",
            "penaltyRate": 0.06,
            "portoFrancoWindow": "weekly",
            "aliases": {},
            "aiEnabled": False,
            "aiProvider": "openai",
            "aiModel": "gpt-4o-mini",
            "aiApiKey": "",
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
    auth = request.headers.get("X-API-Key", "")
    return auth == API_KEY


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


def send_email(subject, body):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        return False, "SMTP non configurato"
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = SMTP_TO
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [SMTP_TO], msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)

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
                "debug": {"host": SMTP_HOST, "port": SMTP_PORT, "user": SMTP_USER, "to": SMTP_TO},
            }
        )
    return jsonify({"ok": True, "delivered": True})


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


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug_mode)
