import json
import os
import sqlite3
import smtplib
import urllib.parse
import urllib.request
import difflib
import re
import secrets
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, redirect
from flask_cors import CORS

# --- CONFIGURAZIONE ---
BASE_DIR = Path(__file__).resolve().parent
DB_PATH_ENV = os.getenv("APP_DB_PATH", "").strip()
if DB_PATH_ENV:
    DB_PATH = Path(DB_PATH_ENV)
else:
    data_dir = Path("/data")
    if data_dir.exists():
        DB_PATH = data_dir / "app_data.db"
    else:
        DB_PATH = BASE_DIR / "app_data.db"
FRONTEND_FILE = BASE_DIR.parent / "index.html"

# Chiavi e Configurazione (GEMINI RIMOSSO - Motore Locale Attivo)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "noreply@seasignorarest.com")
SMTP_TO = os.getenv("SMTP_TO", "amministrazione@seasignorarest.com")
FORMSPREE_ENDPOINT = os.getenv("FORMSPREE_ENDPOINT", "https://formspree.io/f/xykbonje")

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- DATABASE ---
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS app_state (id INTEGER PRIMARY KEY, state TEXT)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_state_versions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts INTEGER NOT NULL, "
            "note TEXT, "
            "state TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ai_weights_audit ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts INTEGER NOT NULL, "
            "actor TEXT, "
            "old_weights TEXT, "
            "new_weights TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS orders_audit ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts INTEGER NOT NULL, "
            "actor TEXT, "
            "action TEXT NOT NULL, "
            "target_list TEXT NOT NULL, "
            "target_id TEXT NOT NULL, "
            "payload TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS suppliers_audit ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts INTEGER NOT NULL, "
            "actor TEXT, "
            "action TEXT NOT NULL, "
            "supplier_id TEXT, "
            "payload TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS email_clicks ("
            "token TEXT PRIMARY KEY, "
            "ts INTEGER NOT NULL, "
            "order_id TEXT, "
            "target_url TEXT NOT NULL, "
            "click_count INTEGER NOT NULL DEFAULT 0, "
            "last_click_ts INTEGER"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS product_intake ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts INTEGER NOT NULL, "
            "reparto TEXT NOT NULL, "
            "name TEXT NOT NULL, "
            "category TEXT NOT NULL, "
            "um TEXT NOT NULL, "
            "supplier_name TEXT, "
            "supplier_price REAL, "
            "supplier_um TEXT, "
            "description TEXT, "
            "image_url TEXT, "
            "specs TEXT, "
            "status TEXT NOT NULL DEFAULT 'PENDING'"
            ")"
        )
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(product_intake)").fetchall()}
            if "supplier_name" not in cols:
                conn.execute("ALTER TABLE product_intake ADD COLUMN supplier_name TEXT")
            if "supplier_price" not in cols:
                conn.execute("ALTER TABLE product_intake ADD COLUMN supplier_price REAL")
            if "supplier_um" not in cols:
                conn.execute("ALTER TABLE product_intake ADD COLUMN supplier_um TEXT")
        except Exception:
            pass
        conn.execute(
            "CREATE TABLE IF NOT EXISTS product_intake_audit ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts INTEGER NOT NULL, "
            "actor TEXT, "
            "action TEXT NOT NULL, "
            "intake_id INTEGER NOT NULL, "
            "payload TEXT"
            ")"
        )
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM app_state")
        count = cur.fetchone()[0]

        default_settings = {
            "brandName": "Sea Signora",
            "color": "#EF7818",
            "homeTitle": "Corporate Home",
            "homeSubtitle": "Benvenuto. Il database è sincronizzato in tempo reale su Railway.",
            "homeVisuals": True,
            "homeCardsEnabled": True,
            "homeCards": {"inbox": "Ordini Inbox", "saving": "Saving Ottimizzato", "catalog": "Catalogo Prodotti"},
            "aiWeights": {"price": 80, "porto": 20},
        }

        if count == 0:
            default_state = {
                "seedVersion": "brand_v1",
                "seededAt": datetime.now().isoformat(),
                "settings": default_settings,
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
            conn.execute(
                "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
                (int(datetime.now().timestamp()), "seed", json.dumps(default_state)),
            )
            conn.commit()
        else:
            row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
            if not row:
                # Tabella popolata ma manca la riga id=1: ricrea in modo sicuro
                default_state = {
                    "seedVersion": "brand_v1",
                    "seededAt": datetime.now().isoformat(),
                    "settings": default_settings,
                    "products": [],
                    "suppliers": [],
                    "reparti": ["Cucina", "Sala", "Bar", "Wine"],
                    "inbox": [],
                    "archive": []
                }
                conn.execute("INSERT INTO app_state (id, state) VALUES (1, ?)", (json.dumps(default_state),))
                conn.commit()
                return

            state = json.loads(row["state"])
            state.setdefault("seedVersion", "brand_v1")
            state.setdefault("seededAt", datetime.now().isoformat())

            settings = state.get("settings") or {}
            # Migrazione legacy: settings.brand -> settings.brandName
            if "brandName" not in settings and "brand" in settings and isinstance(settings["brand"], str):
                settings["brandName"] = settings["brand"]

            # Default non distruttivi (mantiene i valori già impostati)
            for k, v in default_settings.items():
                if k == "homeCards":
                    current_cards = settings.get("homeCards") or {}
                    merged_cards = {**default_settings["homeCards"], **current_cards}
                    settings["homeCards"] = merged_cards
                elif k == "aiWeights":
                    current_w = settings.get("aiWeights") or {}
                    merged_w = {**default_settings["aiWeights"], **current_w}
                    settings["aiWeights"] = merged_w
                else:
                    settings.setdefault(k, v)

            state["settings"] = settings

            suppliers = state.get("suppliers") or []
            if isinstance(suppliers, list):
                base_id = int(datetime.now().timestamp() * 1000)
                changed = False
                for i, s in enumerate(suppliers):
                    if not isinstance(s, dict):
                        continue
                    if s.get("id") is None:
                        s["id"] = base_id + i
                        changed = True
                if changed:
                    state["suppliers"] = suppliers
            conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
            conn.execute(
                "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
                (int(datetime.now().timestamp()), "migrate", json.dumps(state)),
            )
            conn.commit()

init_db()

# --- UTILITIES ---
def validate_ai_weights(weights):
    if not isinstance(weights, dict):
        return False, "aiWeights must be an object"
    price = weights.get("price")
    porto = weights.get("porto")
    if not isinstance(price, (int, float)) or not isinstance(porto, (int, float)):
        return False, "aiWeights.price and aiWeights.porto must be numbers"
    if price < 0 or porto < 0:
        return False, "aiWeights values must be >= 0"
    if int(price + porto) != 100:
        return False, "aiWeights sum must be 100"
    return True, None

def is_admin_request(data):
    role = (data or {}).get("role")
    return role == "admin"

def validate_supplier(s):
    if not isinstance(s, dict):
        return False, "Supplier must be an object"
    name = (s.get("name") or "").strip()
    if not name:
        return False, "Supplier name is required"
    email = (s.get("email") or "").strip()
    if email and "@" not in email:
        return False, "Supplier email is invalid"
    cats = s.get("categories")
    if cats is None:
        return False, "Supplier categories are required"
    if not isinstance(cats, (list, str)):
        return False, "Supplier categories must be a list or string"
    if isinstance(cats, list) and len([c for c in cats if isinstance(c, str) and c.strip()]) == 0:
        return False, "Supplier categories are required"
    if isinstance(cats, str) and len([c for c in cats.split(",") if c.strip()]) == 0:
        return False, "Supplier categories are required"
    return True, None

def get_public_base_url(req):
    env_url = os.getenv("PUBLIC_APP_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    proto = req.headers.get("X-Forwarded-Proto", req.scheme)
    host = req.headers.get("X-Forwarded-Host", req.host)
    return f"{proto}://{host}".rstrip("/")

def send_email_alert(dept, staff, text, admin_link, cta_url=None):
    subject = f"NUOVO ORDINE: {dept} da {staff}"
    body_text = (
        f"Visualizza ordine sull'app (Admin): {admin_link}\n\n"
        f"Reparto: {dept}\n"
        f"Staff: {staff}\n"
        f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"Ordine:\n{text}"
    )
    btn_href = cta_url or admin_link
    body_html = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.5;">
          <p><a href="{btn_href}" style="display:inline-block;background:#1B2F1C;color:#ffffff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:12px;">Visualizza ordine sull'app</a></p>
          <p style="color:#666;font-size:12px;">Se il pulsante non funziona, apri questo link: <a href="{admin_link}">{admin_link}</a></p>
          <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
          <p><b>Reparto:</b> {dept}<br><b>Staff:</b> {staff}<br><b>Data:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
          <pre style="white-space:pre-wrap;background:#f7f7f7;padding:12px;border-radius:12px;border:1px solid #eee;">{text}</pre>
        </div>
    """.strip()
    
    # SMTP
    if SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM or SMTP_USER
            msg["To"] = SMTP_TO
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            msg.attach(MIMEText(body_html, "html", "utf-8"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            return {"sent": True, "channel": "smtp", "to": SMTP_TO, "error": None}
        except Exception as e:
            err = str(e)
            print(f"SMTP Error: {err}")
            smtp_error = err
    else:
        smtp_error = "SMTP credentials missing"
            
    # Formspree Fallback
    if FORMSPREE_ENDPOINT:
        try:
            payload = {
                "_subject": subject,
                "message": body_text,
                "email": SMTP_FROM or SMTP_USER or "noreply@seasignorarest.com",
            }
            data = urllib.parse.urlencode(payload).encode()
            req = urllib.request.Request(
                FORMSPREE_ENDPOINT,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": "SeaSignora/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                _ = resp.read()
            return {"sent": True, "channel": "formspree", "to": SMTP_TO, "error": None}
        except Exception as e:
            err = str(e)
            print(f"Formspree Error: {err}")
            return {"sent": False, "channel": "formspree", "to": SMTP_TO, "error": err}
            
    return {"sent": False, "channel": "smtp", "to": SMTP_TO, "error": smtp_error}

def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.strip().lower()
    m = re.search(r"\b(kg|hg|g|ml|cl|l|pz)\b", u)
    if m:
        u = m.group(1)
    aliases = {
        "g": "g",
        "gr": "g",
        "grammo": "g",
        "grammi": "g",
        "hg": "hg",
        "etto": "hg",
        "kg": "kg",
        "kilo": "kg",
        "l": "l",
        "lt": "l",
        "litro": "l",
        "litri": "l",
        "ml": "ml",
        "cl": "cl",
        "pz": "pz",
        "pezzo": "pz",
        "pezzi": "pz",
    }
    return aliases.get(u, u)

def convert_qty(qty: float, unit_in: str | None, unit_target: str | None) -> float:
    u_in = normalize_unit(unit_in)
    u_t = normalize_unit(unit_target)
    if not u_in or not u_t or u_in == u_t:
        return qty

    # Weight
    if u_in in {"g", "hg", "kg"} and u_t in {"g", "hg", "kg"}:
        # Convert to grams
        grams = qty
        if u_in == "kg":
            grams = qty * 1000
        elif u_in == "hg":
            grams = qty * 100
        # Convert grams to target
        if u_t == "g":
            return grams
        if u_t == "hg":
            return grams / 100
        if u_t == "kg":
            return grams / 1000

    # Volume
    if u_in in {"ml", "cl", "l"} and u_t in {"ml", "cl", "l"}:
        ml = qty
        if u_in == "l":
            ml = qty * 1000
        elif u_in == "cl":
            ml = qty * 10
        if u_t == "ml":
            return ml
        if u_t == "cl":
            return ml / 10
        if u_t == "l":
            return ml / 1000

    return qty

def extract_qty_and_unit(raw_line: str) -> tuple[float, str | None, str]:
    line = raw_line.strip().lower()
    # Pattern handles "500g", "500 g", "0,5kg", "2pz"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|gr|grammi|grammo|hg|etto|l|lt|litri|litro|ml|cl|pz|pezzi|pezzo)\b", line)
    if m:
        qty = float(m.group(1).replace(",", "."))
        unit = normalize_unit(m.group(2))
        cleaned = (line[:m.start()] + " " + line[m.end():]).strip()
        return qty, unit, cleaned

    # Fallback: take first number only
    m2 = re.search(r"(\d+(?:[.,]\d+)?)", line)
    if m2:
        qty = float(m2.group(1).replace(",", "."))
        cleaned = (line[:m2.start()] + " " + line[m2.end():]).strip()
        return qty, None, cleaned

    return 1.0, None, line

def local_smart_parse(text, products):
    """Motore di parsing locale 'Smart Matcher' (senza chiavi API)."""
    items = []
    unmatched = []
    lines = text.split('\n')
    product_names = [p['name'] for p in products]
    product_names_l = [n.lower() for n in product_names]
    product_by_name_l = {p["name"].lower(): p for p in products if isinstance(p.get("name"), str)}
    
    # Parole comuni da ignorare nel match del nome
    stop_words = {'di', 'da', 'il', 'la', 'un', 'una', 'con', 'per', 'kg', 'g', 'gr', 'grammi', 'hg', 'etto', 'l', 'lt', 'litri', 'ml', 'cl', 'casse', 'cassa', 'pz', 'pezzi', 'pezzo'}

    for line in lines:
        raw = line.strip()
        if not raw:
            continue

        qty_in, unit_in, cleaned = extract_qty_and_unit(raw)
        words = cleaned.split()

        clean_words = [w for w in words if w not in stop_words]
        clean_line = " ".join(clean_words).strip()
        
        if not clean_line:
            continue

        # Match fuzzy sul nome prodotto + suggerimenti
        suggestions = difflib.get_close_matches(clean_line, product_names_l, n=5, cutoff=0.2)
        best = suggestions[0] if suggestions else None
        if best and difflib.SequenceMatcher(None, clean_line, best).ratio() >= 0.45:
            p_orig = product_by_name_l.get(best)
            target_um = normalize_unit(p_orig.get("um"))
            if not target_um and unit_in:
                if unit_in in {"g", "hg", "kg"}:
                    target_um = "kg"
                elif unit_in in {"ml", "cl", "l"}:
                    target_um = "l"
                elif unit_in in {"pz"}:
                    target_um = "pz"
            qty = convert_qty(qty_in, unit_in, target_um)
            items.append({
                "productId": p_orig['id'],
                "name": p_orig['name'],
                "qty": qty,
                "um": target_um or p_orig.get("um") or "pz",
                "inputQty": qty_in,
                "inputUm": unit_in,
                "cat": p_orig.get('cat', '')
            })
        else:
            unmatched.append({
                "line": raw,
                "inputQty": qty_in,
                "inputUm": unit_in,
                "clean": clean_line,
                "suggestions": [
                    {
                        "productId": product_by_name_l[s]["id"],
                        "name": product_by_name_l[s]["name"],
                        "cat": product_by_name_l[s].get("cat", ""),
                        "um": product_by_name_l[s].get("um") or "pz",
                    }
                    for s in suggestions
                    if s in product_by_name_l
                ],
            })
    return {"items": items, "unmatched": unmatched}

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
    try:
        data = request.get_json()
        if not data or 'state' not in data:
            return jsonify({"ok": False, "error": "Invalid state"}), 400
        incoming = data["state"]
        force = bool(data.get("force"))
        with get_conn() as conn:
            existing_row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
            existing = json.loads(existing_row["state"]) if existing_row else {}

            if not force:
                ex_p = existing.get("products") or []
                in_p = incoming.get("products") or []
                ex_s = existing.get("suppliers") or []
                in_s = incoming.get("suppliers") or []
                if isinstance(ex_p, list) and isinstance(in_p, list) and len(ex_p) > 0 and len(in_p) == 0:
                    return jsonify({"ok": False, "error": "Refused save: incoming products empty. Use force=true if intended."}), 409
                if isinstance(ex_s, list) and isinstance(in_s, list) and len(ex_s) > 0 and len(in_s) == 0:
                    return jsonify({"ok": False, "error": "Refused save: incoming suppliers empty. Use force=true if intended."}), 409

            if existing_row:
                conn.execute(
                    "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
                    (int(datetime.now().timestamp()), "pre_save", json.dumps(existing)),
                )
            conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(incoming),))
            conn.execute(
                "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
                (int(datetime.now().timestamp()), "save", json.dumps(incoming)),
            )
            conn.execute(
                "DELETE FROM app_state_versions WHERE id NOT IN (SELECT id FROM app_state_versions ORDER BY id DESC LIMIT 300)"
            )
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Save error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/order")
def create_order():
    try:
        data = request.get_json()
        dept = data.get("dept")
        staff = data.get("staff")
        text = data.get("text")
        
        if not dept or not staff or not text:
            return jsonify({"ok": False, "error": "Missing fields"}), 400
            
        with get_conn() as conn:
            row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
            if not row: return jsonify({"ok": False, "error": "Database not initialized"}), 500
            state = json.loads(row['state'])
            
            new_req = {
                "id": int(datetime.now().timestamp() * 1000),
                "dept": dept,
                "staff": staff,
                "text": text,
                "date": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            state["inbox"].insert(0, new_req)
            
            conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
            conn.commit()
            
        base = get_public_base_url(request)
        admin_link = f"{base}/?admin=1&view=dashboard&focus={new_req['id']}"
        token = secrets.token_urlsafe(16)
        cta_url = f"{base}/api/email/click/{token}"
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO email_clicks (token, ts, order_id, target_url, click_count, last_click_ts) VALUES (?, ?, ?, ?, 0, NULL)",
                (token, int(datetime.now().timestamp()), str(new_req["id"]), admin_link),
            )
            conn.commit()
        email = send_email_alert(dept, staff, text, admin_link, cta_url=cta_url)
        
        return jsonify({"ok": True, "notified": bool(email.get("sent")), "email": email})
    except Exception as e:
        print(f"Order error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

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
        ans = "Sono Irina, assistente della compagnia. I prezzi migliori sono evidenziati nel Catalogo Prodotti e nella Heatmap (Prodotti vs Fornitori). Puoi aggiornare i prezzi nella sezione 'Fatture & Storico'."
    elif "ordine" in q or "reparto" in q: 
        ans = "Sono Irina, assistente della compagnia. Gli ordini in attesa sono in Ordini Attivi (sezione Inbox). I reparti ordinano tramite QR code dedicato."
    elif "heatmap" in q:
        ans = "Sono Irina, assistente della compagnia. La Heatmap confronta Prodotti e Fornitori e mette in evidenza il miglior prezzo. Filtra per categoria per lavorare più velocemente."
    elif "trend" in q or "grafic" in q:
        ans = "Sono Irina, assistente della compagnia. Nei report trovi lo storico ordini per reparto e il trend (mensile e trimestrale) con curva morbida."
    else: 
        ans = "Sono Irina, assistente della compagnia. Posso aiutarti a gestire il catalogo, monitorare gli ordini e analizzare i fornitori."
    return jsonify({"ok": True, "answer": ans})

@app.get("/api/diag")
def diagnostics():
    diag = {
        "db": "unknown",
        "db_path": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
        "db_persistent_hint": str(DB_PATH).startswith("/data/") or str(DB_PATH).startswith("/data\\"),
        "engine": "Local Smart Matcher (OK)",
        "email": {
            "smtp_host": SMTP_HOST,
            "smtp_port": SMTP_PORT,
            "smtp_user_present": bool(SMTP_USER),
            "smtp_pass_present": bool(SMTP_PASS),
            "smtp_from": SMTP_FROM,
            "smtp_to": SMTP_TO,
            "formspree_present": bool(FORMSPREE_ENDPOINT),
        },
    }
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM app_state")
            diag["db"] = f"OK (rows: {cur.fetchone()[0]})"
    except Exception as e:
        diag["db"] = f"Error: {str(e)}"
    return jsonify(diag)

@app.get("/api/admin/versions")
def list_versions():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ts, note FROM app_state_versions ORDER BY id DESC LIMIT 50"
        ).fetchall()
        return jsonify(
            {
                "ok": True,
                "versions": [
                    {"id": r["id"], "ts": r["ts"], "note": r["note"]} for r in rows
                ],
            }
        )

@app.post("/api/admin/restore-version")
def restore_version():
    data = request.get_json(silent=True) or {}
    vid = data.get("id")
    if not isinstance(vid, int):
        return jsonify({"ok": False, "error": "Missing version id"}), 400
    with get_conn() as conn:
        row = conn.execute(
            "SELECT state FROM app_state_versions WHERE id = ?", (vid,)
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Version not found"}), 404
        state = json.loads(row["state"])
        existing_row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        if existing_row:
            existing = json.loads(existing_row["state"])
            conn.execute(
                "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
                (int(datetime.now().timestamp()), f"pre_restore_{vid}", json.dumps(existing)),
            )
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.execute(
            "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
            (int(datetime.now().timestamp()), f"restore_{vid}", json.dumps(state)),
        )
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/admin/test-email")
def test_email():
    data = request.get_json(silent=True) or {}
    to_override = data.get("to")
    global SMTP_TO
    original_to = SMTP_TO
    if isinstance(to_override, str) and "@" in to_override:
        SMTP_TO = to_override.strip()
    try:
        base = get_public_base_url(request)
        admin_link = f"{base}/?admin=1&view=dashboard"
        token = secrets.token_urlsafe(16)
        cta_url = f"{base}/api/email/click/{token}"
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO email_clicks (token, ts, order_id, target_url, click_count, last_click_ts) VALUES (?, ?, ?, ?, 0, NULL)",
                (token, int(datetime.now().timestamp()), "TEST", admin_link),
            )
            conn.commit()
        result = send_email_alert("TEST", "Irina", "Questo è un test di invio email alert.", admin_link, cta_url=cta_url)
        return jsonify({"ok": True, "result": result})
    finally:
        SMTP_TO = original_to

@app.get("/api/email/click/<token>")
def email_click(token):
    with get_conn() as conn:
        row = conn.execute("SELECT target_url, click_count FROM email_clicks WHERE token = ?", (token,)).fetchone()
        if not row:
            return redirect(get_public_base_url(request) + "/?admin=1&view=dashboard", code=302)
        conn.execute(
            "UPDATE email_clicks SET click_count = ?, last_click_ts = ? WHERE token = ?",
            (int(row["click_count"] or 0) + 1, int(datetime.now().timestamp()), token),
        )
        conn.commit()
        return redirect(row["target_url"], code=302)

@app.get("/api/admin/email-clicks")
def email_clicks_stats():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT token, ts, order_id, target_url, click_count, last_click_ts FROM email_clicks ORDER BY ts DESC LIMIT 200"
        ).fetchall()
        return jsonify(
            {
                "ok": True,
                "clicks": [
                    {
                        "token": r["token"],
                        "ts": r["ts"],
                        "orderId": r["order_id"],
                        "target": r["target_url"],
                        "clicks": r["click_count"],
                        "lastClickTs": r["last_click_ts"],
                    }
                    for r in rows
                ],
            }
        )

@app.post("/api/public/product-intake")
def product_intake_create():
    data = request.get_json(silent=True) or {}
    reparto = (data.get("reparto") or "").strip()
    name = (data.get("name") or "").strip()
    cat = (data.get("category") or "").strip()
    um = (data.get("um") or "").strip()
    supplier_name = (data.get("supplierName") or "").strip() or None
    supplier_price_raw = data.get("supplierPrice")
    supplier_um = (data.get("supplierUm") or "").strip() or None
    desc = (data.get("description") or "").strip() or None
    image_url = (data.get("imageUrl") or "").strip() or None
    specs = (data.get("specs") or "").strip() or None

    if not reparto or not name or not cat or not um:
        return jsonify({"ok": False, "error": "Missing required fields"}), 400
    supplier_price = None
    if supplier_price_raw is not None and supplier_price_raw != "":
        try:
            supplier_price = float(supplier_price_raw)
        except Exception:
            return jsonify({"ok": False, "error": "Invalid supplierPrice"}), 400
    if not supplier_name or supplier_price is None or supplier_price <= 0 or not supplier_um:
        return jsonify({"ok": False, "error": "Missing supplier data"}), 400

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO product_intake (ts, reparto, name, category, um, supplier_name, supplier_price, supplier_um, description, image_url, specs, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')",
            (int(datetime.now().timestamp()), reparto, name, cat, um, supplier_name, supplier_price, supplier_um, desc, image_url, specs),
        )
        intake_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO product_intake_audit (ts, actor, action, intake_id, payload) VALUES (?, ?, ?, ?, ?)",
            (int(datetime.now().timestamp()), "public", "create", intake_id, json.dumps(data)),
        )
        conn.commit()

    base = get_public_base_url(request)
    admin_link = f"{base}/?admin=1&view=catalog&intake=1"
    send_email_alert(
        "PRODOTTO",
        "QR Import",
        f"Nuovo prodotto proposto:\n- Reparto: {reparto}\n- Nome: {name}\n- Categoria: {cat}\n- UM: {um}\n- Fornitore: {supplier_name}\n- Prezzo: {supplier_price} / {supplier_um}",
        admin_link,
        cta_url=admin_link,
    )
    return jsonify({"ok": True, "id": intake_id})

@app.get("/api/admin/product-intake")
def product_intake_list():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ts, reparto, name, category, um, supplier_name, supplier_price, supplier_um, description, image_url, specs, status FROM product_intake WHERE status = 'PENDING' ORDER BY id DESC LIMIT 500"
        ).fetchall()
        return jsonify(
            {
                "ok": True,
                "items": [
                    {
                        "id": r["id"],
                        "ts": r["ts"],
                        "reparto": r["reparto"],
                        "name": r["name"],
                        "category": r["category"],
                        "um": r["um"],
                        "supplierName": r["supplier_name"],
                        "supplierPrice": r["supplier_price"],
                        "supplierUm": r["supplier_um"],
                        "description": r["description"],
                        "imageUrl": r["image_url"],
                        "specs": r["specs"],
                        "status": r["status"],
                    }
                    for r in rows
                ],
            }
        )

@app.post("/api/admin/product-intake/approve")
def product_intake_approve():
    data = request.get_json(silent=True) or {}
    if not is_admin_request(data):
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    intake_id = data.get("id")
    if not isinstance(intake_id, int):
        return jsonify({"ok": False, "error": "Missing intake id"}), 400
    actor = data.get("actor") or "admin"

    with get_conn() as conn:
        row_intake = conn.execute(
            "SELECT id, reparto, name, category, um, supplier_name, supplier_price, supplier_um, description, image_url, specs FROM product_intake WHERE id = ? AND status = 'PENDING'",
            (intake_id,),
        ).fetchone()
        if not row_intake:
            return jsonify({"ok": False, "error": "Not found"}), 404

        row_state = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        state = json.loads(row_state["state"])

        supplier_name = (row_intake["supplier_name"] or "").strip()
        supplier_price = row_intake["supplier_price"]
        if supplier_name and isinstance(supplier_price, (int, float)):
            suppliers = state.get("suppliers") or []
            if isinstance(suppliers, list):
                exists = any(isinstance(s, dict) and s.get("name") == supplier_name for s in suppliers)
                if not exists:
                    suppliers.append(
                        {
                            "id": int(datetime.now().timestamp() * 1000),
                            "name": supplier_name,
                            "min": 200,
                            "current": 0,
                            "categories": [row_intake["category"]],
                        }
                    )
                    state["suppliers"] = suppliers

        products = state.get("products") or []
        max_id = 0
        for p in products:
            if isinstance(p, dict) and isinstance(p.get("id"), int):
                max_id = max(max_id, p["id"])
        new_id = max_id + 1
        products.append(
            {
                "id": new_id,
                "name": row_intake["name"],
                "cat": row_intake["category"],
                "um": row_intake["um"],
                "desc": row_intake["description"],
                "imageUrl": row_intake["image_url"],
                "specs": row_intake["specs"],
                "prices": {supplier_name: float(supplier_price)} if supplier_name and isinstance(supplier_price, (int, float)) else {},
            }
        )
        state["products"] = products
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.execute("UPDATE product_intake SET status = 'APPROVED' WHERE id = ?", (intake_id,))
        conn.execute(
            "INSERT INTO product_intake_audit (ts, actor, action, intake_id, payload) VALUES (?, ?, ?, ?, ?)",
            (int(datetime.now().timestamp()), actor, "approve", intake_id, json.dumps({"newProductId": new_id})),
        )
        conn.execute(
            "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
            (int(datetime.now().timestamp()), "product_intake_approve", json.dumps(state)),
        )
        conn.commit()

    return jsonify({"ok": True, "productId": new_id})

@app.post("/api/admin/product-intake/reject")
def product_intake_reject():
    data = request.get_json(silent=True) or {}
    if not is_admin_request(data):
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    intake_id = data.get("id")
    if not isinstance(intake_id, int):
        return jsonify({"ok": False, "error": "Missing intake id"}), 400
    actor = data.get("actor") or "admin"
    with get_conn() as conn:
        conn.execute("UPDATE product_intake SET status = 'REJECTED' WHERE id = ?", (intake_id,))
        conn.execute(
            "INSERT INTO product_intake_audit (ts, actor, action, intake_id, payload) VALUES (?, ?, ?, ?, ?)",
            (int(datetime.now().timestamp()), actor, "reject", intake_id, None),
        )
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/admin/delete-order")
def delete_order():
    data = request.get_json(silent=True) or {}
    if not is_admin_request(data):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    target_list = data.get("list")
    target_id = data.get("id")
    actor = data.get("actor") or "admin"

    if target_list not in {"inbox", "archive"}:
        return jsonify({"ok": False, "error": "Invalid list"}), 400
    if target_id is None:
        return jsonify({"ok": False, "error": "Missing id"}), 400

    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        if not row:
            return jsonify({"ok": False, "error": "No state found"}), 404
        state = json.loads(row["state"])

        arr = state.get(target_list) or []
        if not isinstance(arr, list):
            return jsonify({"ok": False, "error": "Invalid state list"}), 500

        before_len = len(arr)
        removed = None

        if target_list == "inbox":
            arr2 = []
            for it in arr:
                if str(it.get("id")) == str(target_id) and removed is None:
                    removed = it
                    continue
                arr2.append(it)
            state["inbox"] = arr2
        else:
            arr2 = []
            for it in arr:
                key = it.get("orderId")
                if key is None:
                    key = it.get("ts")
                if str(key) == str(target_id) and removed is None:
                    removed = it
                    continue
                arr2.append(it)
            state["archive"] = arr2

        if removed is None or len(arr2) == before_len:
            return jsonify({"ok": False, "error": "Order not found"}), 404

        conn.execute(
            "INSERT INTO orders_audit (ts, actor, action, target_list, target_id, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (int(datetime.now().timestamp()), actor, "delete", target_list, str(target_id), json.dumps(removed)),
        )
        conn.execute(
            "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
            (int(datetime.now().timestamp()), f"order_delete_{target_list}", json.dumps(state)),
        )
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.commit()

    return jsonify({"ok": True})

@app.get("/api/admin/orders-audit")
def list_orders_audit():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ts, actor, action, target_list, target_id FROM orders_audit ORDER BY id DESC LIMIT 200"
        ).fetchall()
        return jsonify(
            {
                "ok": True,
                "audit": [
                    {
                        "id": r["id"],
                        "ts": r["ts"],
                        "actor": r["actor"],
                        "action": r["action"],
                        "list": r["target_list"],
                        "target_id": r["target_id"],
                    }
                    for r in rows
                ],
            }
        )

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
        old_settings = state.get("settings") or {}
        new_settings = settings

        new_ai = (new_settings or {}).get("aiWeights")
        if new_ai is not None:
            ok, err = validate_ai_weights(new_ai)
            if not ok:
                return jsonify({"ok": False, "error": err}), 400

        old_ai = (old_settings or {}).get("aiWeights")
        if new_ai is not None and old_ai != new_ai:
            conn.execute(
                "INSERT INTO ai_weights_audit (ts, actor, old_weights, new_weights) VALUES (?, ?, ?, ?)",
                (int(datetime.now().timestamp()), "admin", json.dumps(old_ai), json.dumps(new_ai)),
            )

        state["settings"] = new_settings
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.execute(
            "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
            (int(datetime.now().timestamp()), "settings_save", json.dumps(state)),
        )
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/admin/suppliers")
def update_suppliers():
    data = request.get_json(silent=True) or {}
    if not is_admin_request(data):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    suppliers = data.get("suppliers")
    actor = data.get("actor") or "admin"
    if not isinstance(suppliers, list):
        return jsonify({"ok": False, "error": "Missing suppliers"}), 400

    cleaned = []
    for s in suppliers:
        ok, err = validate_supplier(s)
        if not ok:
            return jsonify({"ok": False, "error": err}), 400
        ss = dict(s)
        if ss.get("id") is None:
            ss["id"] = int(datetime.now().timestamp() * 1000)
        if isinstance(ss.get("categories"), str):
            ss["categories"] = [c.strip() for c in ss["categories"].split(",") if c.strip()]
        cleaned.append(ss)

    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        if not row:
            return jsonify({"ok": False, "error": "No state"}), 404
        state = json.loads(row["state"])

        old_suppliers = state.get("suppliers") or []
        old_by_id = {str(s.get("id")): s for s in old_suppliers if isinstance(s, dict) and s.get("id") is not None}
        new_by_id = {str(s.get("id")): s for s in cleaned if isinstance(s, dict) and s.get("id") is not None}

        def audit(action, supplier_id, payload):
            conn.execute(
                "INSERT INTO suppliers_audit (ts, actor, action, supplier_id, payload) VALUES (?, ?, ?, ?, ?)",
                (int(datetime.now().timestamp()), actor, action, supplier_id, json.dumps(payload) if payload is not None else None),
            )

        # Detect deletions
        for sid, s in old_by_id.items():
            if sid not in new_by_id:
                audit("delete", sid, {"old": s})

        # Detect creates/updates/renames
        rename_map = {}
        for sid, s in new_by_id.items():
            old = old_by_id.get(sid)
            if not old:
                audit("create", sid, {"new": s})
                continue
            old_name = old.get("name")
            new_name = s.get("name")
            if old_name and new_name and old_name != new_name:
                rename_map[old_name] = new_name
                audit("rename", sid, {"from": old_name, "to": new_name})
            if old != s:
                audit("update", sid, {"old": old, "new": s})

        # Apply rename map to product price dictionaries and archived items
        if rename_map:
            products = state.get("products") or []
            for p in products:
                if not isinstance(p, dict):
                    continue
                prices = p.get("prices") or {}
                if not isinstance(prices, dict):
                    continue
                for old_name, new_name in rename_map.items():
                    if old_name in prices and new_name not in prices:
                        prices[new_name] = prices.pop(old_name)
                    elif old_name in prices and new_name in prices:
                        prices.pop(old_name, None)
                p["prices"] = prices
            state["products"] = products

            archive = state.get("archive") or []
            for o in archive:
                if not isinstance(o, dict):
                    continue
                items = o.get("items") or []
                if not isinstance(items, list):
                    continue
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    sup = it.get("supplier")
                    if sup in rename_map:
                        it["supplier"] = rename_map[sup]
            state["archive"] = archive

        # Remove prices for deleted suppliers (by name)
        deleted_names = {s.get("name") for sid, s in old_by_id.items() if sid not in new_by_id and isinstance(s, dict)}
        if deleted_names:
            products = state.get("products") or []
            for p in products:
                if not isinstance(p, dict):
                    continue
                prices = p.get("prices") or {}
                if not isinstance(prices, dict):
                    continue
                for dn in deleted_names:
                    prices.pop(dn, None)
                p["prices"] = prices
            state["products"] = products

        state["suppliers"] = cleaned
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.execute(
            "INSERT INTO app_state_versions (ts, note, state) VALUES (?, ?, ?)",
            (int(datetime.now().timestamp()), "suppliers_save", json.dumps(state)),
        )
        conn.commit()

    return jsonify({"ok": True})

@app.get("/api/admin/suppliers-audit")
def suppliers_audit_list():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ts, actor, action, supplier_id, payload FROM suppliers_audit ORDER BY id DESC LIMIT 200"
        ).fetchall()
        return jsonify(
            {
                "ok": True,
                "audit": [
                    {
                        "id": r["id"],
                        "ts": r["ts"],
                        "actor": r["actor"],
                        "action": r["action"],
                        "supplierId": r["supplier_id"],
                        "payload": json.loads(r["payload"]) if r["payload"] else None,
                    }
                    for r in rows
                ],
            }
        )

@app.get("/api/admin/associations-report")
def associations_report():
    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        if not row:
            return jsonify({"ok": False, "error": "No state"}), 404
        state = json.loads(row["state"])

    products = state.get("products") or []
    suppliers = state.get("suppliers") or []
    supplier_names = {s.get("name") for s in suppliers if isinstance(s, dict) and s.get("name")}
    supplier_names_l = {str(n).lower() for n in supplier_names}

    products_without_suppliers = []
    case_dupes = []
    unknown_suppliers_in_prices = []

    for p in products:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or ""
        prices = p.get("prices")
        if not isinstance(prices, dict) or len(prices) == 0:
            products_without_suppliers.append({"id": p.get("id"), "name": name})
            continue

        keys = [k for k in prices.keys() if isinstance(k, str)]
        lower_map = {}
        dup_groups = []
        for k in keys:
            lk = k.lower()
            lower_map.setdefault(lk, []).append(k)
        for lk, variants in lower_map.items():
            if len(variants) > 1:
                dup_groups.append(variants)
        if dup_groups:
            case_dupes.append({"id": p.get("id"), "product": name, "suppliers": sorted({v for g in dup_groups for v in g})})

        unknown = sorted({k for k in keys if k.lower() not in supplier_names_l})
        if unknown:
            unknown_suppliers_in_prices.append({"id": p.get("id"), "product": name, "suppliers": unknown})

    return jsonify(
        {
            "ok": True,
            "counts": {
                "productsWithoutSuppliers": len(products_without_suppliers),
                "caseDuplicates": len(case_dupes),
                "unknownSuppliers": len(unknown_suppliers_in_prices),
            },
            "productsWithoutSuppliers": products_without_suppliers,
            "caseDuplicateAssociations": case_dupes,
            "unknownSuppliersInPrices": unknown_suppliers_in_prices,
        }
    )

@app.post("/api/admin/migrate")
def migrate_state():
    try:
        default_settings = {
            "brandName": "Sea Signora",
            "color": "#EF7818",
            "homeTitle": "Corporate Home",
            "homeSubtitle": "Benvenuto. Il database è sincronizzato in tempo reale su Railway.",
            "homeVisuals": True,
            "homeCardsEnabled": True,
            "homeCards": {"inbox": "Ordini Inbox", "saving": "Saving Ottimizzato", "catalog": "Catalogo Prodotti"},
            "aiWeights": {"price": 80, "porto": 20},
        }

        with get_conn() as conn:
            row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
            if not row:
                return jsonify({"ok": False, "error": "No state found"}), 404
            state = json.loads(row["state"])
            state.setdefault("seedVersion", "brand_v1")
            state.setdefault("seededAt", datetime.now().isoformat())

            settings = state.get("settings") or {}
            if "brandName" not in settings and "brand" in settings and isinstance(settings["brand"], str):
                settings["brandName"] = settings["brand"]
            for k, v in default_settings.items():
                if k == "homeCards":
                    current_cards = settings.get("homeCards") or {}
                    settings["homeCards"] = {**default_settings["homeCards"], **current_cards}
                elif k == "aiWeights":
                    current_w = settings.get("aiWeights") or {}
                    settings["aiWeights"] = {**default_settings["aiWeights"], **current_w}
                else:
                    settings.setdefault(k, v)
            state["settings"] = settings

            conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
            conn.commit()

        return jsonify({"ok": True, "seedVersion": state.get("seedVersion")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/admin/ai-audit")
def ai_audit_list():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ts, actor, old_weights, new_weights FROM ai_weights_audit ORDER BY id DESC LIMIT 100"
        ).fetchall()
        return jsonify(
            {
                "ok": True,
                "audit": [
                    {
                        "id": r["id"],
                        "ts": r["ts"],
                        "actor": r["actor"],
                        "old": json.loads(r["old_weights"]) if r["old_weights"] else None,
                        "new": json.loads(r["new_weights"]) if r["new_weights"] else None,
                    }
                    for r in rows
                ],
            }
        )

# --- SERVING FRONTEND ---
@app.route("/")
def index():
    resp = send_from_directory(FRONTEND_FILE.parent, "index.html")
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.get("/catalogo-master")
def redirect_catalogo_master():
    return redirect("/?admin=1&view=catalog", code=301)

@app.get("/catalog-master")
def redirect_catalog_master():
    return redirect("/?admin=1&view=catalog", code=301)

@app.get("/assets/<path:filename>")
def assets(filename):
    assets_dir = FRONTEND_FILE.parent / "assets"
    return send_from_directory(assets_dir, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
