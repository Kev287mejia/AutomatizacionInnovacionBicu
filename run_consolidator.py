#!/usr/bin/env python
"""
run_consolidator.py

Lanzador Institucional del Consolidador Word BICU (Fase 14.9).
Permite iniciar la aplicación de escritorio directamente desde la raíz del proyecto.
"""

import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.word_consolidator.ui.app import main

if __name__ == "__main__":
    main()
