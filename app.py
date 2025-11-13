"""
A simple proxy server, based on original by gear11:
https://gist.github.com/gear11/8006132
Modified from original to support both GET and POST, status code passthrough, header and form data passthrough.
Usage: http://hostname:port/p/(URL to be proxied, minus protocol)
For example: http://localhost:5000/p/www.google.com
"""
import re
from urllib.parse import urlparse, urlunparse
from flask import Flask, render_template, request, abort, Response, redirect, jsonify
import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

DS_TOKEN = os.getenv("DS_TOKEN")
DS_TARGET = os.getenv("DS_TARGET")



app = Flask(__name__.split('.')[0])
logging.basicConfig(level=logging.INFO)
APPROVED_HOSTS = set(["www.demarches-simplifiees.fr"])
CHUNK_SIZE = 1024
LOG = logging.getLogger("app.py")

@app.route('/')
def index():
    """Serve a simple HTML page with a token field and JS that reads a document ID
    from a Grist table (via the `/grist/doc-id` endpoint) and issues a POST on submit.
    """
    return render_template(
        'index.html',
        LABEL_TABLE=os.getenv("LABEL_TABLE"),
        DOSSIERS_TABLE=os.getenv("DOSSIERS_TABLE")
    )

@app.route('/create', methods=['POST'])
def create_post():
    """Receive POSTs from the page. Expects JSON: { token: string, docId: string }.

    If TARGET_POST_URL environment variable is set, this endpoint will forward the
    token/docId as a JSON POST to that URL and return the proxied response. If not
    set, it simply echoes back the received payload for debugging.
    """

    payload = request.get_json(force=True, silent=True)

    if not payload:
        return jsonify({'error': 'Expected JSON body with docId and query'}), 400
    if not DS_TARGET:
        return jsonify({'received': payload})
    
     # Standard headers for JSON payload
    headers = {
        "Content-Type": "application/json"
    }

    query = payload.get('query')

    # Add Authorization header if token is provided
    if DS_TOKEN:
        headers["Authorization"] = f"Bearer {DS_TOKEN}"

    try:
        r = requests.post(DS_TARGET,  json={"query": query}, headers=headers, timeout=10)
        return Response(
            r.text,                     # decode content to string
            status=r.status_code,
            mimetype="application/json" # sets Content-Type header
        )
    
    except Exception as e:
        LOG.exception('Failed to forward POST')
        return jsonify({'error': 'Failed to forward POST', 'detail': str(e)}), 502

