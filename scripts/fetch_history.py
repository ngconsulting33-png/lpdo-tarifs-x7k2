#!/usr/bin/env python3
"""Récupère l'historique des cours (une valeur par jour) dans le dernier site publié.

Le site publié contient data/prices.enc.json (chiffré). On le télécharge, on le déchiffre avec
SITE_PASSPHRASE et on garde la clé « historique ». Ne doit JAMAIS faire échouer le relevé :
en cas de problème (premier lancement, réseau...), on écrit {} et on continue.

Usage : python3 scripts/fetch_history.py sortie.json
"""
import base64
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(dst):
    hist = {}
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import encrypt_json as E
        depot = os.environ["GITHUB_REPOSITORY"]            # ex. ngconsulting33-png/lpdo-tarifs-x7k2
        owner, repo = depot.split("/", 1)
        url = f"https://{owner.lower()}.github.io/{repo}/data/prices.enc.json?t={os.getpid()}"
        enc = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lpdo-releve"}), timeout=30))
        b = base64.b64decode
        clair = AESGCM(E.cle(os.environ["SITE_PASSPHRASE"])).decrypt(b(enc["iv"]), b(enc["ct"]), None)
        hist = json.loads(clair).get("historique") or {}
        print(f"historique récupéré : {len(hist)} jour(s)")
    except Exception as e:  # noqa: BLE001
        print("pas d'historique (", str(e)[:120], ") : on repart de zéro")
    json.dump(hist, open(dst, "w"))


if __name__ == "__main__":
    main(sys.argv[1])
