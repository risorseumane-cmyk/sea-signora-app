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

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app_data.db"
FRONTEND_FILE = BASE_DIR.parent / "index.html"

# Chiavi e Configurazione
raw_key = os.getenv("GEMINI_API_KEY", "").replace('"', '').replace("'", "").strip()
GEMINI_API_KEY = raw_key or "AIzaSyB1onn5YUyBbgAJEd7jxqq5lol3myLpNsg"

print(f"--- SERVER STARTUP ---")
print(f"BASE_DIR: {BASE_DIR}")
print(f"DB_PATH: {DB_PATH}")
print(f"FRONTEND_FILE: {FRONTEND_FILE} (exists: {FRONTEND_FILE.exists()})")
print(f"GEMINI_API_KEY length: {len(GEMINI_API_KEY) if GEMINI_API_KEY else 0}")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@seasignorarest.com")
SMTP_TO = os.getenv("SMTP_TO", "Amministrazione@seasignorarest.com")
FORMSPREE_ENDPOINT = os.getenv("FORMSPREE_ENDPOINT", "")

app = Flask(__name__)
CORS(app)

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def get_default_state():
    return {
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

def init_db():
    try:
        with get_conn() as conn:
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
            
            cur.execute("SELECT state_json FROM app_state WHERE id = 1")
            row = cur.fetchone()
            
            if row is None or not json.loads(row["state_json"]).get("products"):
                print("Inizializzazione database con prodotti predefiniti...")
                cur.execute(
                    "INSERT OR REPLACE INTO app_state (id, state_json, updated_at) VALUES (1, ?, ?)",
                    (json.dumps(get_default_state()), datetime.utcnow().isoformat()),
                )
            conn.commit()
    except Exception as e:
        print(f"Errore inizializzazione DB: {e}")

def sanitize_state(state):
    if not isinstance(state, dict): return {}
    safe = dict(state)
    settings = dict(safe.get("settings") or {})
    settings.pop("serverApiKey", None)
    settings.pop("aiApiKey", None)
    settings.pop("serverUrl", None)
    safe["settings"] = settings
    return safe

def send_email(subject, body):
    # Fallback email simplified
    print(f"EMAIL MOCK: {subject}")
    return True, ""

def log_notification(kind, subject, body, delivered, error_text=""):
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO notification_log (kind, subject, body, delivered, error, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (kind, subject, body, 1 if delivered else 0, error_text, datetime.utcnow().isoformat())
            )
            conn.commit()
    except: pass

def get_gemini_response(prompt):
    """Urllib fallback direct for stability on Railway."""
    if not GEMINI_API_KEY: 
        print("Gemini API Key missing")
        return None
    
    # Try different versions/endpoints if 404 happens
    endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent?key={GEMINI_API_KEY}"
    ]
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    last_err = ""
    
    for url in endpoints:
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res['candidates'][0]['content']['parts'][0]['text']
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            print(f"Gemini API Error ({url.split('/')[-2]}): {e.code} - {err_msg}")
            last_err = f"HTTP {e.code}: {err_msg}"
            continue
        except Exception as e:
            print(f"Gemini Error ({url.split('/')[-2]}): {e}")
            last_err = f"Error: {str(e)}"
            continue
            
    print(f"Gemini Fallback Failed. Last error: {last_err}")
    return last_err # Return error message instead of None for diagnostics

print("Backend booting... Checking DB and environment...")
init_db()
print(f"Gemini API Key present: {bool(GEMINI_API_KEY)}")
@app.get("/api/state")
def get_state():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT state_json, updated_at FROM app_state WHERE id = 1")
        row = cur.fetchone()
    if not row: return jsonify({"ok": False, "error": "State not found"}), 404
    return jsonify({"ok": True, "state": sanitize_state(json.loads(row["state_json"]))})

@app.post("/api/state")
def save_state():
    state = request.get_json().get("state")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE app_state SET state_json = ?, updated_at = ? WHERE id = 1", (json.dumps(state), datetime.utcnow().isoformat()))
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/order")
def create_order():
    payload = request.get_json()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT state_json FROM app_state WHERE id = 1")
        state = json.loads(cur.fetchone()["state_json"])
        order = {"id": int(datetime.utcnow().timestamp()*1000), "staff": payload.get("staff"), "dept": payload.get("dept"), "text": payload.get("text"), "date": datetime.utcnow().strftime("%H:%M:%S")}
        state.setdefault("inbox", []).append(order)
        cur.execute("UPDATE app_state SET state_json = ?, updated_at = ? WHERE id = 1", (json.dumps(state), datetime.utcnow().isoformat()))
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/ai/order-parse")
def ai_parse():
    p = request.get_json()
    prompt = f"Catalog: {json.dumps(p.get('catalog'))}\nOrder: {p.get('text')}\nReturn JSON: {{\"items\":[{{\"productId\":ID,\"qty\":NUM,\"name\":\"NAME\"}}]}}"
    res = get_gemini_response(prompt)
    if not res or res.startswith("HTTP") or res.startswith("Error"): 
        return jsonify({"ok": False, "error": res or "Unknown Gemini error"}), 502
    try:
        start, end = res.find("{"), res.rfind("}")
        return jsonify({"ok": True, "parsed": json.loads(res[start:end+1])})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "raw": res}), 502

@app.post("/api/ai/help")
def ai_help():
    data = request.get_json()
    q = data.get("question")
    ctx = data.get("context", {})
    prompt = f"User Question: {q}\nContext: {json.dumps(ctx)}\nBe helpful, concise, and professional. You are the AI assistant for Sea Signora restaurant logistics."
    res = get_gemini_response(prompt)
    if not res or res.startswith("HTTP") or res.startswith("Error"):
        return jsonify({"ok": False, "error": res or "Gemini error"}), 502
    return jsonify({"ok": True, "answer": res})

@app.post("/api/admin/suppliers")
def update_suppliers():
    data = request.get_json()
    new_suppliers = data.get("suppliers")
    if not new_suppliers: return jsonify({"ok": False, "error": "No suppliers data"}), 400
    
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT state_json FROM app_state WHERE id = 1")
        state = json.loads(cur.fetchone()["state_json"])
        state["suppliers"] = new_suppliers
        cur.execute("UPDATE app_state SET state_json = ?, updated_at = ? WHERE id = 1", (json.dumps(state), datetime.utcnow().isoformat()))
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/admin/page-settings")
def update_page_settings():
    data = request.get_json()
    new_settings = data.get("settings")
    if not new_settings: return jsonify({"ok": False, "error": "No settings data"}), 400
    
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT state_json FROM app_state WHERE id = 1")
        state = json.loads(cur.fetchone()["state_json"])
        state["settings"] = {**state.get("settings", {}), **new_settings}
        cur.execute("UPDATE app_state SET state_json = ?, updated_at = ? WHERE id = 1", (json.dumps(state), datetime.utcnow().isoformat()))
        conn.commit()
    return jsonify({"ok": True})

@app.get("/api/diag")
def diagnostics():
    diag = {"db": "unknown", "gemini": "unknown", "key_present": bool(GEMINI_API_KEY), "key_prefix": GEMINI_API_KEY[:6] if GEMINI_API_KEY else ""}
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM app_state")
            diag["db"] = f"OK (rows: {cur.fetchone()[0]})"
    except Exception as e:
        diag["db"] = f"Error: {str(e)}"
    
    test_res = get_gemini_response("Say 'OK'")
    if test_res and "OK" in test_res.upper():
        diag["gemini"] = "OK"
    else:
        # If fallback failed, show the specific error from the last attempt
        diag["gemini"] = f"Failed: {test_res}"
    
    return jsonify(diag)

@app.post("/api/admin/reset-db")
def reset_db():
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM app_state")
            cur.execute("DELETE FROM notification_log")
            cur.execute("INSERT INTO app_state (id, state_json, updated_at) VALUES (1, ?, ?)", (json.dumps(get_default_state()), datetime.utcnow().isoformat()))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Reset DB Error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/")
def serve():
    return send_from_directory(FRONTEND_FILE.parent, FRONTEND_FILE.name)

@app.get("/assets/<path:path>")
def serve_assets(path):
    return send_from_directory(FRONTEND_FILE.parent / "assets", path)

