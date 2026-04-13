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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyB1onn5YUyBbgAJEd7jxqq5lol3myLpNsg").strip()
# ...
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
            {"id": 1, "name": "Aragosta Viva", "cat": "Ittico", "um": "500-700g", "prices": {"METRO": 73.80}},
            {"id": 2, "name": "Aragosta Viva", "cat": "Ittico", "um": "250-400g", "prices": {"OROBICA": 72.00}},
            {"id": 3, "name": "Astice Polpa", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 91.00}},
            {"id": 4, "name": "Astice Canada vivo", "cat": "Ittico", "um": "kg", "prices": {"LINEA MARE": 29.50}},
            {"id": 5, "name": "Astice Blu Vivo", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 65.90}},
            {"id": 6, "name": "Astice Jumbo", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 63.00}},
            {"id": 7, "name": "Carabineros 8/10", "cat": "Ittico", "um": "kg", "prices": {"REACH FOOD": 102.00}},
            {"id": 8, "name": "Gambero Fondale", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 13.00}},
            {"id": 9, "name": "Gambero Rosa", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 16.50}},
            {"id": 10, "name": "Gambero Viola 2°", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 56.00}},
            {"id": 11, "name": "Gambero Rosso 2°", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 59.00}},
            {"id": 12, "name": "Leg King Crab Cotto", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 79.00}},
            {"id": 13, "name": "Leg King Crab Crudo", "cat": "Ittico", "um": "kg", "prices": {"REACH FOOD": 100.00}},
            {"id": 14, "name": "King Crab Vivo", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 93.00}},
            {"id": 15, "name": "King Crab Polpa", "cat": "Ittico", "um": "kg", "prices": {"REACH FOOD": 56.50}},
            {"id": 16, "name": "Moleca", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 165.00}},
            {"id": 17, "name": "Scampo 1/5", "cat": "Ittico", "um": "kg", "prices": {"REACH FOOD": 65.00}},
            {"id": 18, "name": "Scampo 21/30", "cat": "Ittico", "um": "kg", "prices": {"METRO": 10.62}},
            {"id": 19, "name": "Scampo 31/40", "cat": "Ittico", "um": "kg", "prices": {"METRO": 14.08}},
            {"id": 20, "name": "Mazzancolla Fresca", "cat": "Ittico", "um": "kg", "prices": {"METRO": 12.49}},
            {"id": 21, "name": "Mazzancolla Gelo", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 7.50}},
            {"id": 22, "name": "Berice", "cat": "Ittico", "um": "500-700g", "prices": {"METRO": 20.00}},
            {"id": 23, "name": "Branzino Grecia", "cat": "Ittico", "um": "kg", "prices": {"METRO": 11.71}},
            {"id": 24, "name": "Branzino Grecia", "cat": "Ittico", "um": "1,5-2kg", "prices": {"METRO": 13.25}},
            {"id": 25, "name": "Branzino Grecia", "cat": "Ittico", "um": "1,8-2,6kg", "prices": {"METRO": 20.93}},
            {"id": 26, "name": "Dentice Gibboso", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 23.50}},
            {"id": 27, "name": "Gallinella", "cat": "Ittico", "um": "kg", "prices": {"METRO": 21.15}},
            {"id": 28, "name": "Ombrina Boccadoro 4+", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 14.50}},
            {"id": 29, "name": "Orata Grecia", "cat": "Ittico", "um": "600-800g", "prices": {"METRO": 10.18}},
            {"id": 30, "name": "Orata Grecia", "cat": "Ittico", "um": "1-1,5 Kg", "prices": {"METRO": 12.22}},
            {"id": 31, "name": "Ricciola 3-4 kg", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 20.90}},
            {"id": 32, "name": "Rombo Fresco Francia", "cat": "Ittico", "um": "800-1kg", "prices": {"METRO": 19.90}},
            {"id": 33, "name": "Rombo Fresco Francia", "cat": "Ittico", "um": "1-1,5kg", "prices": {"METRO": 19.90}},
            {"id": 34, "name": "Salmone affum. Norvegese", "cat": "Ittico", "um": "1 kg", "prices": {"OROBICA": 28.50}},
            {"id": 35, "name": "Scorfano Portogallo", "cat": "Ittico", "um": "600-800g", "prices": {"LINEA MARE": 26.80}},
            {"id": 36, "name": "Sogliola Francia", "cat": "Ittico", "um": "400-600g", "prices": {"METRO": 27.00}},
            {"id": 37, "name": "Akami -60", "cat": "Ittico", "um": "kg", "prices": {"REACH FOOD": 49.50}},
            {"id": 38, "name": "Otoro -60", "cat": "Ittico", "um": "kg", "prices": {"REACH FOOD": 65.00}},
            {"id": 39, "name": "Chutoro -60", "cat": "Ittico", "um": "kg", "prices": {"REACH FOOD": 53.50}},
            {"id": 40, "name": "Tonno Rosso Mediterraneo Fresco Ikejime", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 37.00}},
            {"id": 41, "name": "Tonno Rosso Fuentes Fresco", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 29.00}},
            {"id": 42, "name": "Cannolicchi Estero", "cat": "Ittico", "um": "kg", "prices": {"METRO": 7.50}},
            {"id": 43, "name": "Cappasanta 1/2 guscio fresca", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 11.90}},
            {"id": 44, "name": "Tartufi di Mare", "cat": "Ittico", "um": "kg", "prices": {"METRO": 11.12}},
            {"id": 45, "name": "Vongola Verace", "cat": "Ittico", "um": "kg", "prices": {"LINEA MARE": 18.70}},
            {"id": 46, "name": "Cockles", "cat": "Ittico", "um": "kg", "prices": {"METRO": 3.67}},
            {"id": 47, "name": "Vongola Lupino", "cat": "Ittico", "um": "kg", "prices": {"METRO": 8.09}},
            {"id": 48, "name": "Vongola Tellina", "cat": "Ittico", "um": "kg", "prices": {"METRO": 10.49}},
            {"id": 49, "name": "Cozze", "cat": "Ittico", "um": "kg", "prices": {"METRO": 3.50}},
            {"id": 50, "name": "Ostriche Gillardeau N3", "cat": "Ittico", "um": "pz", "prices": {"LINEA MARE": 2.44}},
            {"id": 51, "name": "Ostriche OR N4", "cat": "Ittico", "um": "pz", "prices": {"OYSTER OASIS": 2.25}},
            {"id": 52, "name": "Ostriche Perla del Delta N3", "cat": "Ittico", "um": "pz", "prices": {"OYSTER OASIS": 2.85}},
            {"id": 53, "name": "Ostriche Mignon di Goro N6", "cat": "Ittico", "um": "pz", "prices": {"OROBICA": 0.69}},
            {"id": 54, "name": "Ostriche Perlina del Delta N 6", "cat": "Ittico", "um": "pz", "prices": {"OYSTER OASIS": 1.05}},
            {"id": 55, "name": "Calamaro Spillo Mediterraneo Gelo", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 22.80}},
            {"id": 56, "name": "Calamaro Patagonia Gelo", "cat": "Ittico", "um": "kg", "prices": {"LINEA MARE": 7.40}},
            {"id": 57, "name": "Polpo Gelo Indopacifico T3", "cat": "Ittico", "um": "kg", "prices": {"LINEA MARE": 16.95}},
            {"id": 58, "name": "Polpo Gelo Mediterraneo T4", "cat": "Ittico", "um": "kg", "prices": {"METRO": 17.85}},
            {"id": 59, "name": "Lumaca di Mare", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 17.90}},
            {"id": 60, "name": "Riccio Polpa Gelo", "cat": "Ittico", "um": "kg", "prices": {"REACH FOOD": 21.00}},
            {"id": 61, "name": "Riccio Fresco Galizia", "cat": "Ittico", "um": "kg", "prices": {"OROBICA": 27.90}},
            {"id": 62, "name": "Caviale Osetra", "cat": "Ittico", "um": "50g", "prices": {"REACH FOOD": 43.00}},
            {"id": 63, "name": "Colatura di Alici", "cat": "Ittico", "um": "100ml", "prices": {"MARR": 6.99}},
            {"id": 64, "name": "Aglio Bianco", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 5.90}},
            {"id": 65, "name": "Agretto", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 7.30}},
            {"id": 66, "name": "Asparagi", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 10.50}},
            {"id": 67, "name": "Capperi Pernice", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 25.00}},
            {"id": 68, "name": "Carciofi Mammola", "cat": "Vegetali", "um": "pz", "prices": {"OROBICA": 1.18}},
            {"id": 69, "name": "Carciofi Spina", "cat": "Vegetali", "um": "pz", "prices": {"ABBASCIÀ": 1.38}},
            {"id": 70, "name": "Carote", "cat": "Vegetali", "um": "kg", "prices": {"OROBICA": 1.29}},
            {"id": 71, "name": "Carote Ciuffo", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 3.50}},
            {"id": 72, "name": "Catalogna", "cat": "Vegetali", "um": "kg", "prices": {"MARR": 2.16}},
            {"id": 73, "name": "Cavolfiore", "cat": "Vegetali", "um": "kg", "prices": {"ARRIGONI": 2.40}},
            {"id": 74, "name": "Cavolo Nero", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 3.30}},
            {"id": 75, "name": "Cetrioli", "cat": "Vegetali", "um": "kg", "prices": {"ARRIGONI": 3.00}},
            {"id": 76, "name": "Cime di Rapa", "cat": "Vegetali", "um": "kg", "prices": {"MARR": 2.20}},
            {"id": 77, "name": "Cipolle Tropea", "cat": "Vegetali", "um": "kg", "prices": {"ABBASCIÀ": 2.20}},
            {"id": 78, "name": "Cipolline Borretane", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 4.90}},
            {"id": 79, "name": "Cipolle Bianche", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 1.35}},
            {"id": 80, "name": "Cipollotto Tropea", "cat": "Vegetali", "um": "kg", "prices": {"MARR": 3.30}},
            {"id": 81, "name": "Crauti Verdi", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 1.20}},
            {"id": 82, "name": "Daikon", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 1.50}},
            {"id": 83, "name": "Fave", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 3.90}},
            {"id": 84, "name": "Finocchi", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 1.50}},
            {"id": 85, "name": "Indivia Belga", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 2.00}},
            {"id": 86, "name": "Indivia Scarola", "cat": "Vegetali", "um": "kg", "prices": {"ARRIGONI": 4.00}},
            {"id": 87, "name": "Lattuga Romana", "cat": "Vegetali", "um": "kg", "prices": {"OROBICA": 2.12}},
            {"id": 88, "name": "Mizuna", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 3.00}},
            {"id": 89, "name": "Melanzane", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 2.00}},
            {"id": 90, "name": "Patate", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 0.90}},
            {"id": 91, "name": "Peperoncino Corno", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 5.90}},
            {"id": 92, "name": "Piselli freschi", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 7.90}},
            {"id": 93, "name": "Jalapenos Rossi", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 6.90}},
            {"id": 94, "name": "Peperoni Friggitelli", "cat": "Vegetali", "um": "kg", "prices": {"MARR": 4.12}},
            {"id": 95, "name": "Peperoni Italia", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 3.90}},
            {"id": 96, "name": "Pomodoro Ramato", "cat": "Vegetali", "um": "kg", "prices": {"ARRIGONI": 2.00}},
            {"id": 97, "name": "Pomodoro Riccio", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 8.90}},
            {"id": 98, "name": "Pomodoro Datterino", "cat": "Vegetali", "um": "kg", "prices": {"FAST FRUIT": 3.50}},
            {"id": 99, "name": "Pomodoro Marinda", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 5.90}},
            {"id": 100, "name": "Pomodori Zebrini", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 6.90}},
            {"id": 101, "name": "Pomodoro Datterino Giallo", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 5.90}},
            {"id": 102, "name": "Pomodoro S.Martino", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 4.50}},
            {"id": 103, "name": "Porro", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 2.15}},
            {"id": 104, "name": "Radicchio Variegato", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 4.90}},
            {"id": 105, "name": "Scalogno", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 6.00}},
            {"id": 106, "name": "Sedano", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 1.50}},
            {"id": 107, "name": "Verza", "cat": "Vegetali", "um": "kg", "prices": {"MARR": 1.18}},
            {"id": 108, "name": "Zucchine", "cat": "Vegetali", "um": "kg", "prices": {"ABBASCIÀ": 2.28}},
            {"id": 109, "name": "Ananas", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 2.90}},
            {"id": 110, "name": "Arance Succo (Navel)", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 1.80}},
            {"id": 111, "name": "Arance Tarocco", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 2.00}},
            {"id": 112, "name": "Avocado", "cat": "Vegetali", "um": "pz", "prices": {"ORTOLANO": 1.50}},
            {"id": 113, "name": "Bergamotto", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 6.90}},
            {"id": 114, "name": "Cachi Israele", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 4.90}},
            {"id": 115, "name": "Clementine", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 4.90}},
            {"id": 116, "name": "Lamponi", "cat": "Vegetali", "um": "125g", "prices": {"ORTOLANO": 4.50}},
            {"id": 117, "name": "Limoni", "cat": "Vegetali", "um": "kg", "prices": {"MARR": 2.20}},
            {"id": 118, "name": "Limoni Foglia", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 2.50}},
            {"id": 119, "name": "Lime", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 3.98}},
            {"id": 120, "name": "Mele", "cat": "Vegetali", "um": "kg", "prices": {"ABBASCIÀ": 2.30}},
            {"id": 121, "name": "Mirtilli", "cat": "Vegetali", "um": "125g", "prices": {"ORTOLANO": 3.25}},
            {"id": 122, "name": "Pompelmo", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 1.80}},
            {"id": 123, "name": "Ribes", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 60.00}},
            {"id": 124, "name": "Melograni", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 3.90}},
            {"id": 125, "name": "Acetosella", "cat": "Vegetali", "um": "100g", "prices": {"ORTOLANO": 6.30}},
            {"id": 126, "name": "Aneto", "cat": "Vegetali", "um": "60g", "prices": {"ABBASCIÀ": 1.18}},
            {"id": 127, "name": "Basilico", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 15.50}},
            {"id": 128, "name": "Coriandolo", "cat": "Vegetali", "um": "100g", "prices": {"FAST FRUIT": 1.20}},
            {"id": 129, "name": "Dragoncello FR", "cat": "Vegetali", "um": "100g", "prices": {"ORTOLANO": 5.90}},
            {"id": 130, "name": "Erba Cipollina", "cat": "Vegetali", "um": "100g", "prices": {"ORTOLANO": 3.50}},
            {"id": 131, "name": "Fiori Eduli", "cat": "Vegetali", "um": "60g", "prices": {"ORTOLANO": 4.30}},
            {"id": 132, "name": "Galanga", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 4.90}},
            {"id": 133, "name": "Germoglio Pisello", "cat": "Vegetali", "um": "pz", "prices": {"ORTOLANO": 2.90}},
            {"id": 134, "name": "Menta Ananas", "cat": "Vegetali", "um": "60g", "prices": {"ORTOLANO": 5.90}},
            {"id": 135, "name": "Finocchio Marino", "cat": "Vegetali", "um": "100g", "prices": {"ORTOLANO": 19.00}},
            {"id": 136, "name": "Funghi Champignon", "cat": "Vegetali", "um": "kg", "prices": {"ARRIGONI": 3.00}},
            {"id": 137, "name": "Prezzemolo", "cat": "Vegetali", "um": "kg", "prices": {"ORTOLANO": 4.90}},
            {"id": 138, "name": "Origano Secco", "cat": "Vegetali", "um": "40g", "prices": {"ORTOLANO": 2.50}},
            {"id": 139, "name": "Shiso", "cat": "Vegetali", "um": "15g", "prices": {"ORTOLANO": 3.50}},
            {"id": 140, "name": "Timo", "cat": "Vegetali", "um": "100g", "prices": {"FAST FRUIT": 1.18}},
            {"id": 141, "name": "Zenzero", "cat": "Vegetali", "um": "kg", "prices": {"MARR": 4.12}},
            {"id": 142, "name": "Pasta Staff", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 1.16}},
            {"id": 143, "name": "Riso Carnaroli", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 1.41}},
            {"id": 144, "name": "Riso Basmati", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 2.60}},
            {"id": 145, "name": "Riso Sushi", "cat": "Consumabili", "um": "kg", "prices": {"JFC": 2.10}},
            {"id": 146, "name": "Linguine Felicetti", "cat": "Consumabili", "um": "500g", "prices": {"GRANCHEF": 3.68}},
            {"id": 147, "name": "Mezzemaniche Mancini", "cat": "Consumabili", "um": "500g", "prices": {"DE AMICIS": 2.14}},
            {"id": 148, "name": "Fusilloni Cavalieri", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 1.99}},
            {"id": 149, "name": "Gnocchi Patate Staff", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 1.70}},
            {"id": 150, "name": "Cous Cous Staff", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 2.60}},
            {"id": 151, "name": "Paccheri Mancini (6kg)", "cat": "Consumabili", "um": "kg", "prices": {"DE AMICIS": 4.28}},
            {"id": 152, "name": "Carne Trita 80/20", "cat": "Consumabili", "um": "kg", "prices": {"CARNI NOBILI": 10.00}},
            {"id": 153, "name": "Salsiccia", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 5.85}},
            {"id": 154, "name": "Hamburger Manzo", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 8.40}},
            {"id": 155, "name": "Pollo", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 3.60}},
            {"id": 156, "name": "Pollo Coscia", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 2.40}},
            {"id": 157, "name": "Pollo Petto", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 6.40}},
            {"id": 158, "name": "Polpette bovino", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 8.60}},
            {"id": 159, "name": "Fesa Tacchino fresca", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 8.90}},
            {"id": 160, "name": "Coppa Maiale", "cat": "Consumabili", "um": "kg", "prices": {"CARNI NOBILI": 4.80}},
            {"id": 161, "name": "Stinchi Maiale 1/2", "cat": "Consumabili", "um": "pz", "prices": {"MARR": 3.17}},
            {"id": 162, "name": "Nuggets di Pollo", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 4.98}},
            {"id": 163, "name": "Cordon Bleu Pollo", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 4.86}},
            {"id": 164, "name": "Ossa Manzo", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 4.50}},
            {"id": 165, "name": "Ossa Agnello", "cat": "Consumabili", "um": "kg", "prices": {"DE AMICIS": 2.38}},
            {"id": 166, "name": "Cosce Agnello", "cat": "Consumabili", "um": "kg", "prices": {"DE AMICIS": 17.01}},
            {"id": 167, "name": "Costolette d'agnello", "cat": "Consumabili", "um": "kg", "prices": {"CARNI NOBILI": 32.00}},
            {"id": 168, "name": "Lardo", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 9.20}},
            {"id": 169, "name": "Prosciutto Cotto 1°Q", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 7.49}},
            {"id": 170, "name": "Magatello Wagyu", "cat": "Consumabili", "um": "kg", "prices": {"CARNI NOBILI": 18.00}},
            {"id": 171, "name": "Controfiletto Angus", "cat": "Consumabili", "um": "kg", "prices": {"CARNI NOBILI": 33.15}},
            {"id": 172, "name": "Parmigiano 24M", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 18.90}},
            {"id": 173, "name": "Parmigiano V. Rosse", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 28.40}},
            {"id": 174, "name": "Mix formaggi Staff", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 6.40}},
            {"id": 175, "name": "Gorgonzola", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 6.40}},
            {"id": 176, "name": "Edamer", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 3.50}},
            {"id": 177, "name": "Burro", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 6.05}},
            {"id": 178, "name": "Panna 38%", "cat": "Consumabili", "um": "lt", "prices": {"METRO": 4.55}},
            {"id": 179, "name": "Mascarpone", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 6.17}},
            {"id": 180, "name": "Latte Intero UHT", "cat": "Consumabili", "um": "lt", "prices": {"METRO": 0.86}},
            {"id": 181, "name": "Uova Intere (90 pz)", "cat": "Consumabili", "um": "conf", "prices": {"METRO": 16.24}},
            {"id": 182, "name": "Uova di Quaglia (18 pz)", "cat": "Consumabili", "um": "conf", "prices": {"METRO": 2.90}},
            {"id": 183, "name": "Uova Tuorlo", "cat": "Consumabili", "um": "lt", "prices": {"MARR": 7.80}},
            {"id": 184, "name": "Misto d'Uovo", "cat": "Consumabili", "um": "lt", "prices": {"METRO": 3.51}},
            {"id": 185, "name": "Albume d'Uovo", "cat": "Consumabili", "um": "lt", "prices": {"MARR": 2.60}},
            {"id": 186, "name": "Yogurt Greco 10%", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 4.50}},
            {"id": 187, "name": "Feta Greca", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 6.30}},
            {"id": 188, "name": "Provola", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 7.60}},
            {"id": 189, "name": "Fontina", "cat": "Consumabili", "um": "kg", "prices": {"DE AMICIS": 17.58}},
            {"id": 190, "name": "Formaggio spalmabile", "cat": "Consumabili", "um": "1,5kg", "prices": {"MARR": 6.40}},
            {"id": 191, "name": "Stracciatella", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 9.70}},
            {"id": 192, "name": "Olio Girasole", "cat": "Consumabili", "um": "10lt", "prices": {"METRO": 16.66}},
            {"id": 193, "name": "Capperi in aceto", "cat": "Consumabili", "um": "700g", "prices": {"METRO": 2.80}},
            {"id": 194, "name": "Passata Pomodoro", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 1.28}},
            {"id": 195, "name": "Zucchero Canna", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 1.83}},
            {"id": 196, "name": "Zucchero Bianco", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 1.05}},
            {"id": 197, "name": "Olive dolci", "cat": "Consumabili", "um": "kg", "prices": {"ORTOLANO": 7.90}},
            {"id": 198, "name": "Olive Riviera", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 10.50}},
            {"id": 199, "name": "Miele", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 5.80}},
            {"id": 200, "name": "Cioccolato Emilia B.", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 18.40}},
            {"id": 201, "name": "Cacao Amaro", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 19.00}},
            {"id": 202, "name": "Colatura di Alici", "cat": "Consumabili", "um": "150ml", "prices": {"MARR": 6.99}},
            {"id": 203, "name": "Nocciole sgusciate tostate", "cat": "Consumabili", "um": "N/D", "prices": {"METRO": 20.50}},
            {"id": 204, "name": "Farina 00", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 0.69}},
            {"id": 205, "name": "Farina Nuvola", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 1.28}},
            {"id": 206, "name": "Peperoncino Goccia", "cat": "Consumabili", "um": "conf", "prices": {"DE AMICIS": 9.50}},
            {"id": 207, "name": "Pane Hamburgher", "cat": "Consumabili", "um": "conf", "prices": {"MARR": 1.80}},
            {"id": 208, "name": "Trancetti Tonno", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 6.63}},
            {"id": 209, "name": "Filetti Acciughe", "cat": "Consumabili", "um": "720g", "prices": {"MARR": 10.10}},
            {"id": 210, "name": "Mais dolce", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 1.20}},
            {"id": 211, "name": "Amarene Fabbri", "cat": "Consumabili", "um": "kg 1,25", "prices": {"METRO": 22.49}},
            {"id": 212, "name": "Brandy", "cat": "Consumabili", "um": "70cl", "prices": {"METRO": 5.00}},
            {"id": 213, "name": "Vodka Cucina", "cat": "Consumabili", "um": "lt", "prices": {"METRO": 9.90}},
            {"id": 214, "name": "Purea di Lampone", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 10.99}},
            {"id": 215, "name": "Pane Gluten free 24pz", "cat": "Consumabili", "um": "ct", "prices": {"MARR": 16.50}},
            {"id": 216, "name": "Umeboshi", "cat": "Consumabili", "um": "kg", "prices": {"JFC": 23.00}},
            {"id": 217, "name": "Patate Chips", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 3.23}},
            {"id": 218, "name": "Piselli", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 2.32}},
            {"id": 219, "name": "Contorno Verdure", "cat": "Consumabili", "um": "kg", "prices": {"DE AMICIS": 2.20}},
            {"id": 220, "name": "Broccoli Rosette", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 2.00}},
            {"id": 221, "name": "Buste Sottov. S", "cat": "Consumabili", "um": "100pz", "prices": {"MARR": 4.98}},
            {"id": 222, "name": "Buste Sottov. M", "cat": "Consumabili", "um": "100pz", "prices": {"MARR": 11.86}},
            {"id": 223, "name": "Etichette 100x50", "cat": "Consumabili", "um": "500pz", "prices": {"METRO": 10.00}},
            {"id": 224, "name": "Squeezer 490/760ml", "cat": "Consumabili", "um": "6pz", "prices": {"METRO": 8.90}},
            {"id": 225, "name": "Rotoli carta cassa", "cat": "Consumabili", "um": "10pz", "prices": {"METRO": 18.00}},
            {"id": 226, "name": "Rotoli carta pos", "cat": "Consumabili", "um": "12pz", "prices": {"METRO": 6.50}},
            {"id": 227, "name": "Risma carta A4", "cat": "Consumabili", "um": "10pz", "prices": {"METRO": 15.50}},
            {"id": 228, "name": "Bobina Carta", "cat": "Consumabili", "um": "pz", "prices": {"MARR": 3.20}},
            {"id": 229, "name": "Guanti Neri", "cat": "Consumabili", "um": "100pz", "prices": {"METRO": 3.90}},
            {"id": 230, "name": "Guanti Neri XL", "cat": "Consumabili", "um": "100pz", "prices": {"METRO": 3.90}},
            {"id": 231, "name": "Sac a Poche", "cat": "Consumabili", "um": "100pz", "prices": {"MARR": 18.60}},
            {"id": 232, "name": "Pellicola 300m", "cat": "Consumabili", "um": "rot", "prices": {"MARR": 6.95}},
            {"id": 233, "name": "Salviette umide", "cat": "Consumabili", "um": "conf.", "prices": {"METRO": 9.99}},
            {"id": 234, "name": "Sacchi neutri", "cat": "Consumabili", "um": "20pz", "prices": {"METRO": 2.01}},
            {"id": 235, "name": "Carta da forno fogli", "cat": "Consumabili", "um": "5kg", "prices": {"METRO": 26.00}},
            {"id": 236, "name": "Zafferano", "cat": "Consumabili", "um": "40b.", "prices": {"DE AMICIS": 32.00}},
            {"id": 237, "name": "Pepe Nero", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 12.00}},
            {"id": 238, "name": "Sale Maldon", "cat": "Consumabili", "um": "570g", "prices": {"MARR": 10.25}},
            {"id": 239, "name": "Sale", "cat": "Consumabili", "um": "kg", "prices": {"MARR": 0.40}},
            {"id": 240, "name": "Cumino", "cat": "Consumabili", "um": "kg", "prices": {"METRO": 20.71}},
            {"id": 241, "name": "Curcuma", "cat": "Consumabili", "um": "600g", "prices": {"METRO": 1.63}},
            {"id": 242, "name": "Sapone refill Arancia di Capri", "cat": "Cleaning", "um": "N/D", "prices": {"ACQUA DI PARMA": 33.00}},
            {"id": 243, "name": "Crema refill Arancia di Capri", "cat": "Cleaning", "um": "N/D", "prices": {"ACQUA DI PARMA": 33.00}},
            {"id": 244, "name": "Diffusore 180ml Arancia di Capri", "cat": "Cleaning", "um": "N/D", "prices": {"ACQUA DI PARMA": 66.50}},
            {"id": 245, "name": "Diffusore 500ml Colonia", "cat": "Cleaning", "um": "N/D", "prices": {"ACQUA DI PARMA": 126.00}},
            {"id": 246, "name": "Profumo sala Dyptique", "cat": "Cleaning", "um": "N/D", "prices": {"DYPTIQUE": 65.00}},
            {"id": 247, "name": "Carta Igienica Clienti 56PZ", "cat": "Cleaning", "um": "N/D", "prices": {"MARR": 0.27}},
            {"id": 248, "name": "Collottorio Clienti", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 2.88}},
            {"id": 249, "name": "Filo Interdentale Monouso 200PZ", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 8.19}},
            {"id": 250, "name": "Assorbenti Interni", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 3.53}},
            {"id": 251, "name": "Salviette Fria Clienti", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 10.90}},
            {"id": 252, "name": "Detergente lavastoviglie 10L", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 10.00}},
            {"id": 253, "name": "Brillantante lavastoviglie 5L", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 7.50}},
            {"id": 254, "name": "Sapone piatti concentrato 5L", "cat": "Cleaning", "um": "N/D", "prices": {"MARR": 5.00}},
            {"id": 255, "name": "Anticalcare Cucina 10L", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 23.00}},
            {"id": 256, "name": "Disinfettante superfici 5L", "cat": "Cleaning", "um": "N/D", "prices": {"MARR": 8.52}},
            {"id": 257, "name": "Sgrassante Cucina 5L", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 8.90}},
            {"id": 258, "name": "Sgorgante L", "cat": "Cleaning", "um": "N/D", "prices": {"ICA SYSTEM": 3.35}},
            {"id": 259, "name": "Lucido Acciaio 750ml", "cat": "Cleaning", "um": "N/D", "prices": {"PANARIELLO": 11.61}},
            {"id": 260, "name": "Detergente Bicchieri 12KG", "cat": "Cleaning", "um": "N/D", "prices": {"WINTERHALTER": 75.00}},
            {"id": 261, "name": "Brillantante Bicchieri 10KG", "cat": "Cleaning", "um": "N/D", "prices": {"WINTERHALTER": 83.50}},
            {"id": 262, "name": "Panni microfibra 5pz", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 9.20}},
            {"id": 263, "name": "Spugna abrasiva Giallo/verde 10pz", "cat": "Cleaning", "um": "N/D", "prices": {"WINTERHALTER": 4.00}},
            {"id": 264, "name": "Vetri e Pavimenti 5L", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 11.85}},
            {"id": 265, "name": "Detergente WC PZ", "cat": "Cleaning", "um": "N/D", "prices": {"WINTERHALTER": 2.10}},
            {"id": 266, "name": "Detergente Bagno PZ", "cat": "Cleaning", "um": "N/D", "prices": {"PANARIELLO": 4.00}},
            {"id": 267, "name": "Asciugamani a V (5000PZ)", "cat": "Cleaning", "um": "N/D", "prices": {"PANARIELLO": 44.55}},
            {"id": 268, "name": "Sacco Gialli 300PZ", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 26.25}},
            {"id": 269, "name": "Sacco Neutro 500PZ", "cat": "Cleaning", "um": "N/D", "prices": {"PANARIELLO": 48.50}},
            {"id": 270, "name": "Sacco Umido 200PZ", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 58.00}},
            {"id": 271, "name": "Carta Igienica Staff", "cat": "Cleaning", "um": "N/D", "prices": {"WINTERHALTER": 17.00}},
            {"id": 272, "name": "Detersivo Liquido Biancheria 5L", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 9.44}},
            {"id": 273, "name": "Ammorbidente Liquido Biancheria 5L", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 5.75}},
            {"id": 274, "name": "Candeggina 12L", "cat": "Cleaning", "um": "N/D", "prices": {"METRO": 6.00}},
            {"id": 275, "name": "Perborato polvere 4kg", "cat": "Cleaning", "um": "N/D", "prices": {"PANARIELLO": 29.00}},
            {"id": 276, "name": "REMY M. 1738 A.R", "cat": "Spirits", "um": "L", "prices": {"N/D": 59.63}},
            {"id": 277, "name": "BRANDY FUNDADOR 15", "cat": "Spirits", "um": "L", "prices": {"N/D": 67.37}},
            {"id": 278, "name": "ARMAGNAC CASTAREDE XO 20YO", "cat": "Spirits", "um": "L", "prices": {"N/D": 86.76}},
            {"id": 279, "name": "COGNAC PASQUET LOT 58 FINE SPIRITS CASK 52,4°", "cat": "Spirits", "um": "L", "prices": {"N/D": 389.66}},
            {"id": 280, "name": "DROUIN AOC", "cat": "Spirits", "um": "L", "prices": {"N/D": 28.22}},
            {"id": 281, "name": "ABELHA SILVER ORGANIC 39°", "cat": "Spirits", "um": "L", "prices": {"N/D": 36.38}},
            {"id": 282, "name": "PISCO 1615 MOSTO VERDE ITALIA", "cat": "Spirits", "um": "L", "prices": {"N/D": 49.10}},
            {"id": 283, "name": "ABELHA GOLD ORGANIC 39°", "cat": "Spirits", "um": "L", "prices": {"N/D": 51.26}},
            {"id": 284, "name": "GRAPPA BAROLO", "cat": "Spirits", "um": "L", "prices": {"N/D": 57.86}},
            {"id": 285, "name": "GRAPPA TRIPLE A", "cat": "Spirits", "um": "L", "prices": {"N/D": 59.96}},
            {"id": 286, "name": "GRAPPA UVA MOSCATO GIALLO", "cat": "Spirits", "um": "L", "prices": {"N/D": 98.08}},
            {"id": 287, "name": "GRAPPA CAPOVILLA LAST CENTURY ERMINIA", "cat": "Spirits", "um": "L", "prices": {"N/D": 125.14}},
            {"id": 288, "name": "CAPOVILLA AMARENE", "cat": "Spirits", "um": "L", "prices": {"N/D": 195.28}},
            {"id": 289, "name": "CHARTREUSE CENTENAIRE", "cat": "Spirits", "um": "L", "prices": {"N/D": 55.76}},
            {"id": 290, "name": "CHARTREUSE R. DE L.", "cat": "Spirits", "um": "L", "prices": {"N/D": 89.09}},
            {"id": 291, "name": "CHARTREUSE V.E.P.", "cat": "Spirits", "um": "L", "prices": {"N/D": 122.04}},
            {"id": 292, "name": "RUM PROVIDENCE BLANC", "cat": "Spirits", "um": "L", "prices": {"N/D": 30.71}},
            {"id": 293, "name": "OKINAWA RUM", "cat": "Spirits", "um": "L", "prices": {"N/D": 37.46}},
            {"id": 294, "name": "RUM BLACK TOT", "cat": "Spirits", "um": "L", "prices": {"N/D": 40.60}},
            {"id": 295, "name": "RENEGADE CANE RUM", "cat": "Spirits", "um": "L", "prices": {"N/D": 47.10}},
            {"id": 296, "name": "RUM DIPLOMATICO PLANAS", "cat": "Spirits", "um": "L", "prices": {"N/D": 47.20}},
            {"id": 297, "name": "RUM DIPLOMATICO RESERVA", "cat": "Spirits", "um": "L", "prices": {"N/D": 32.99}},
            {"id": 298, "name": "RHUM PAPA ROUYO 1 YO", "cat": "Spirits", "um": "L", "prices": {"N/D": 71.26}},
            {"id": 299, "name": "BRUGAL COLECCION VISIONARIA 01", "cat": "Spirits", "um": "L", "prices": {"N/D": 96.58}},
            {"id": 300, "name": "BRUGAL MAESTRO RISERVA", "cat": "Spirits", "um": "L", "prices": {"N/D": 144.26}},
            {"id": 301, "name": "RHUM HAVANA 15Y", "cat": "Spirits", "um": "L", "prices": {"N/D": 162.86}},
            {"id": 302, "name": "HERRADURA PLATA 0.7", "cat": "Spirits", "um": "L", "prices": {"N/D": 41.38}},
            {"id": 303, "name": "HERRADURA REPOSADO", "cat": "Spirits", "um": "L", "prices": {"N/D": 44.57}},
            {"id": 304, "name": "TEQUILA TAPATIO REPOSADO", "cat": "Spirits", "um": "L", "prices": {"N/D": 53.04}},
            {"id": 305, "name": "MEZCAL LOST EXPLORER 8", "cat": "Spirits", "um": "L", "prices": {"N/D": 58.86}},
            {"id": 306, "name": "MEZCAL DERRUMBES ZACATECAS", "cat": "Spirits", "um": "L", "prices": {"N/D": 63.37}},
            {"id": 307, "name": "TEQUILA THE LOST EXPLORER TEQUILA BLANCO 40°", "cat": "Spirits", "um": "L", "prices": {"N/D": 63.68}},
            {"id": 308, "name": "TEQUILA DON FULANO BLANCO FUERTE 50°", "cat": "Spirits", "um": "L", "prices": {"N/D": 66.67}},
            {"id": 309, "name": "MEZCAL PALENQUE TOBAZICHE JUAN HERNANDEZ", "cat": "Spirits", "um": "L", "prices": {"N/D": 75.26}},
            {"id": 310, "name": "DON FULANO ANEJO 40°", "cat": "Spirits", "um": "L", "prices": {"N/D": 80.00}},
            {"id": 311, "name": "LA VENENOSA SIERRA DEL TIGRE", "cat": "Spirits", "um": "L", "prices": {"N/D": 106.67}},
            {"id": 312, "name": "THE LOST EXPLORER SALMIANA 42°", "cat": "Spirits", "um": "L", "prices": {"N/D": 154.41}},
            {"id": 313, "name": "TEQUILA DON FULANO IMPERIAL 40°", "cat": "Spirits", "um": "L", "prices": {"N/D": 184.22}},
            {"id": 314, "name": "CLASSE AZUL AHUMADO", "cat": "Spirits", "um": "L", "prices": {"N/D": 341.08}},
            {"id": 315, "name": "TEQUILA CLASSE AZUL GOLD", "cat": "Spirits", "um": "L", "prices": {"N/D": 507.51}},
            {"id": 316, "name": "CLASSE AZUL SAN LOUIS", "cat": "Spirits", "um": "L", "prices": {"N/D": 515.71}},
            {"id": 317, "name": "AMARAS LOGIA ANCESTRAL", "cat": "Spirits", "um": "L", "prices": {"N/D": 561.97}},
            {"id": 318, "name": "VODKA BELUGA NOBLE", "cat": "Spirits", "um": "L", "prices": {"N/D": 43.55}},
            {"id": 319, "name": "VODKA ELIT", "cat": "Spirits", "um": "L", "prices": {"N/D": 45.90}},
            {"id": 320, "name": "VODKA BELUGA TRANSALT", "cat": "Spirits", "um": "L", "prices": {"N/D": 53.39}},
            {"id": 321, "name": "VODKA BELUGA ALLURE", "cat": "Spirits", "um": "L", "prices": {"N/D": 123.46}},
            {"id": 322, "name": "CHOPIN FAMILY RESERVE VODKA", "cat": "Spirits", "um": "L", "prices": {"N/D": 184.21}},
            {"id": 323, "name": "VODKA BELUGA GOLD LINE", "cat": "Spirits", "um": "L", "prices": {"N/D": 187.95}},
            {"id": 324, "name": "WOODFORD BOURBON", "cat": "Spirits", "um": "L", "prices": {"N/D": 42.54}},
            {"id": 325, "name": "WOODFORD RESERVE RYE", "cat": "Spirits", "um": "L", "prices": {"N/D": 43.02}},
            {"id": 326, "name": "JACK DANIEL SINGLE BARREL", "cat": "Spirits", "um": "L", "prices": {"N/D": 44.74}},
            {"id": 327, "name": "WATERFORD CUVEE ARGOT", "cat": "Spirits", "um": "L", "prices": {"N/D": 54.93}},
            {"id": 328, "name": "W&M GLENLOSSIE 2010 PX FINISH 46°", "cat": "Spirits", "um": "L", "prices": {"N/D": 56.11}},
            {"id": 329, "name": "KILKERRAN 12YO 46°", "cat": "Spirits", "um": "L", "prices": {"N/D": 58.57}},
            {"id": 330, "name": "KILCHOMAN MACHIR BAY", "cat": "Spirits", "um": "L", "prices": {"N/D": 58.40}},
            {"id": 331, "name": "MICHTERS AMERICAN UNBLENDED", "cat": "Spirits", "um": "L", "prices": {"N/D": 61.03}},
            {"id": 332, "name": "GLENFIDDICH XX", "cat": "Spirits", "um": "L", "prices": {"N/D": 63.29}},
            {"id": 333, "name": "CU BOCAN CREATION #6 46°", "cat": "Spirits", "um": "L", "prices": {"N/D": 64.29}},
            {"id": 334, "name": "LONGROW PEATED 46° CL 70", "cat": "Spirits", "um": "L", "prices": {"N/D": 66.40}},
            {"id": 335, "name": "LOCHLEA PLOUGHING EDITION 46°", "cat": "Spirits", "um": "L", "prices": {"N/D": 69.54}},
            {"id": 336, "name": "W&M CAOL ILA 10YO", "cat": "Spirits", "um": "L", "prices": {"N/D": 74.99}},
            {"id": 337, "name": "MIYAGIKYO NO AGE", "cat": "Spirits", "um": "L", "prices": {"N/D": 79.13}},
            {"id": 338, "name": "FEW IMMORTAL OOLONG TEA", "cat": "Spirits", "um": "L", "prices": {"N/D": 83.46}},
            {"id": 339, "name": "COPPERWORKS AMERICAN SINGLE", "cat": "Spirits", "um": "L", "prices": {"N/D": 88.10}},
            {"id": 340, "name": "MACALLAN 12 DOUBLE CASK", "cat": "Spirits", "um": "L", "prices": {"N/D": 88.78}},
            {"id": 341, "name": "W&M CASK GLEN ELGIN 15YO", "cat": "Spirits", "um": "L", "prices": {"N/D": 91.99}},
            {"id": 342, "name": "BUNNAHABHAIN STAOISHA 9YO", "cat": "Spirits", "um": "L", "prices": {"N/D": 93.61}},
            {"id": 343, "name": "SPRINGBANK 15YO 46°", "cat": "Spirits", "um": "L", "prices": {"N/D": 99.11}},
            {"id": 344, "name": "HIBIKI HARMONY", "cat": "Spirits", "um": "L", "prices": {"N/D": 100.80}},
            {"id": 345, "name": "LAKES - THE WHISKYMAKER'S", "cat": "Spirits", "um": "L", "prices": {"N/D": 102.03}},
            {"id": 346, "name": "W&M CAOL ILA 15YO", "cat": "Spirits", "um": "L", "prices": {"N/D": 103.20}},
            {"id": 347, "name": "KILCHOMAN PX 2023 EDITION 50°", "cat": "Spirits", "um": "L", "prices": {"N/D": 106.67}},
            {"id": 348, "name": "SPRINGBANK 10YO FINO", "cat": "Spirits", "um": "L", "prices": {"N/D": 112.86}},
            {"id": 349, "name": "MICHTER'S US*1 TOASTED", "cat": "Spirits", "um": "L", "prices": {"N/D": 116.11}},
            {"id": 350, "name": "SHIZUOKA UNITED S FIRST", "cat": "Spirits", "um": "L", "prices": {"N/D": 152.44}},
            {"id": 351, "name": "PORT ASKAIG 17", "cat": "Spirits", "um": "L", "prices": {"N/D": 154.07}},
            {"id": 352, "name": "OCTOMORE 16.1", "cat": "Spirits", "um": "L", "prices": {"N/D": 162.56}},
            {"id": 353, "name": "ICHIRO DOUBLE DISTILLERIES", "cat": "Spirits", "um": "L", "prices": {"N/D": 165.71}},
            {"id": 354, "name": "MARS KOMAGATAKE SHINSU SINGLE CA", "cat": "Spirits", "um": "L", "prices": {"N/D": 216.71}}
        ],
        "suppliers": [
            {"name": "METRO", "min": 150, "current": 0},
            {"name": "OROBICA", "min": 250, "current": 0},
            {"name": "LINEA MARE", "min": 200, "current": 0},
            {"name": "REACH FOOD", "min": 300, "current": 0},
            {"name": "MARR", "min": 200, "current": 0},
            {"name": "ORTOLANO", "min": 100, "current": 0},
            {"name": "OYSTER OASIS", "min": 150, "current": 0},
            {"name": "ARRIGONI", "min": 100, "current": 0},
            {"name": "ABBASCIÀ", "min": 120, "current": 0},
            {"name": "FAST FRUIT", "min": 100, "current": 0},
            {"name": "JFC", "min": 300, "current": 0},
            {"name": "GRANCHEF", "min": 200, "current": 0},
            {"name": "DE AMICIS", "min": 150, "current": 0},
            {"name": "CARNI NOBILI", "min": 250, "current": 0},
            {"name": "ACQUA DI PARMA", "min": 500, "current": 0},
            {"name": "DYPTIQUE", "min": 300, "current": 0},
            {"name": "ICA SYSTEM", "min": 200, "current": 0},
            {"name": "PANARIELLO", "min": 150, "current": 0},
            {"name": "WINTERHALTER", "min": 400, "current": 0}
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
    cur.execute("SELECT state_json FROM app_state WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO app_state (id, state_json, updated_at) VALUES (1, ?, ?)",
            (json.dumps(default_state), datetime.utcnow().isoformat()),
        )
    else:
        # Se il database esiste già ma non ha prodotti, forziamo il caricamento del catalogo
        current_state = json.loads(row["state_json"])
        num_products = len(current_state.get("products") or [])
        print(f"DB già inizializzato con {num_products} prodotti.")
        if not current_state.get("products") or num_products < 10:
            print("Database vuoto o con pochi prodotti, forzo il caricamento del catalogo completo...")
            cur.execute(
                "UPDATE app_state SET state_json = ?, updated_at = ? WHERE id = 1",
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

    subject = f"[Sea Signora] NUOVO ORDINE da {dept}"
    body = (
        f"🚨 AVVISO NUOVO ORDINE\n\n"
        f"Reparto: {dept}\n"
        f"Inviato da: {staff}\n"
        f"Data/Ora: {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC\n\n"
        f"--- TESTO DELL'ORDINE ---\n"
        f"{text}\n"
        f"-------------------------\n\n"
        f"Puoi gestire questo ordine e confrontare i prezzi qui: https://seasignora-ordini.up.railway.app"
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
