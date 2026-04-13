import sys
import os
from pathlib import Path

# Aggiungi la cartella backend al path per poter importare app
backend_path = str(Path(__file__).resolve().parent / "backend")
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
