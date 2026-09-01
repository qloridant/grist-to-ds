# Serveur Python (back-end) de l'appli "Grist to DS" : sert le widget
# (route /) et fait proxy vers l'API DS pour contourner CORS (route
# /create). Détails complets dans le README.md.
import re
from urllib.parse import urlparse, urlunparse
# Flask est le micro-framework web Python qui fait tourner le serveur.
from flask import Flask, render_template, request, abort, Response, redirect, jsonify
import os
import requests  # bibliothèque pour faire des appels HTTP sortants (vers Démarches Simplifiées)
import logging
# python-dotenv : permet de lire un fichier .env local et de charger son
# contenu comme variables d'environnement (os.getenv(...)). Voir le
# README pour l'explication complète du fichier .env.
from dotenv import load_dotenv

# Charge les variables du fichier .env (s'il existe) dans l'environnement
# du processus. En production (Scalingo), il n'y a pas de fichier .env :
# les variables sont configurées directement dans l'interface Scalingo,
# mais l'effet est le même (elles sont lues via os.getenv).
load_dotenv()

# Variables d'environnement lues une seule fois, au démarrage du
# processus. Un changement du fichier .env ou de la config Scalingo ne
# sera pris en compte qu'après redémarrage du serveur.
LABEL_TABLE = os.getenv("LABEL_TABLE", "").strip()
DS_TOKEN = os.getenv("DS_TOKEN", "").strip()
DS_TARGET = os.getenv("DS_TARGET", "").strip()

# Création de l'application Flask (le serveur web en lui-même).
app = Flask(__name__.split('.')[0])
logging.basicConfig(level=logging.INFO)
# Liste blanche d'hôtes autorisés pour le proxy (mesure de sécurité,
# hérité du proxy générique d'origine).
APPROVED_HOSTS = set(["www.demarches-simplifiees.fr"])
CHUNK_SIZE = 1024
LOG = logging.getLogger("app.py")

@app.route('/')
def index():
    # Sert le HTML/JS du widget (templates/index.html) après avoir
    # vérifié que les variables d'environnement nécessaires sont bien là.
    # Note : DOSSIERS_TABLE n'est plus lue ici, elle est détectée
    # dynamiquement côté navigateur (voir templates/index.html), car son
    # nom varie selon la démarche synchronisée dans chaque document Grist.
    if not LABEL_TABLE:
        return "❌ LABEL_TABLE manquante", 500
    if not DS_TOKEN:
        return "❌ DS_TOKEN manquant", 500
    if not DS_TARGET:
        return "❌ DS_TARGET manquant", 500

    # render_template va chercher templates/index.html, remplacer le
    # {{ LABEL_TABLE }} qu'il contient par la valeur ci-dessus (moteur de
    # templates Jinja2 fourni par Flask), puis renvoyer le HTML final au
    # navigateur.
    return render_template(
        'index.html',
        LABEL_TABLE=LABEL_TABLE
    )

@app.route('/create', methods=['POST'])
def create_post():
    # Le proxy : reçoit la requête GraphQL du widget (même domaine, pas
    # de CORS) et la relaie vers l'API DS avec le token secret DS_TOKEN.
    payload = request.get_json(force=True, silent=True)

    if not payload:
        return jsonify({'error': 'Expected JSON body with docId and query'}), 400

    if not DS_TARGET:
        return jsonify({'error': 'DS_TARGET manquant'}), 500

    # Standard headers for JSON payload
    headers = {
        "Content-Type": "application/json"
    }

    query = payload.get('query')

    # Add Authorization header if token is provided
    if DS_TOKEN:
        headers["Authorization"] = f"Bearer {DS_TOKEN}"

    try:
        # Appel réel, côté serveur, vers l'API GraphQL de Démarches
        # Simplifiées (DS_TARGET). C'est cet appel qui serait bloqué par
        # CORS s'il était fait directement depuis le JS du navigateur.
        r = requests.post(DS_TARGET,  json={"query": query}, headers=headers, timeout=10)
        return Response(
            r.text,                     # decode content to string
            status=r.status_code,
            mimetype="application/json" # sets Content-Type header
        )

    except Exception as e:
        LOG.exception('Failed to forward POST')
        return jsonify({'error': 'Failed to forward POST', 'detail': str(e)}), 502
