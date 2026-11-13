import os
import sys

# Agrega el directorio de la aplicación al path de Python para Passenger en cPanel
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from core.wsgi import application

