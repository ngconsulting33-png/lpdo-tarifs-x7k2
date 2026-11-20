#!/usr/bin/env python3
"""Chiffre prices.json avec le mot de passe de l'agence (secret SITE_PASSPHRASE).

AES-256-GCM, clé dérivée par PBKDF2-SHA256 (600 000 itérations). Le navigateur déchiffre avec
la même méthode (Web Crypto) : sans le mot de passe, le fichier publié est illisible.

Usage : SITE_PASSPHRASE=... python3 scripts/encrypt_json.py entree.json sortie.enc.json
"""
import base64
import hashlib
import json
import os
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITER = 600_000
SALT = hashlib.sha256(b"lpdo-tarifs-v1").digest()[:16]  # fixe : la clé mémorisée reste valable d'une mise à jour à l'autre


def cle(mdp):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=SALT, iterations=ITER).derive(mdp.encode("utf-8"))


def chiffrer(data: bytes, mdp: str) -> dict:
    iv = os.urandom(12)
    ct = AESGCM(cle(mdp)).encrypt(iv, data, None)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return {"v": 1, "iter": ITER, "salt": b64(SALT), "iv": b64(iv), "ct": b64(ct)}


if __name__ == "__main__":
    mdp = os.environ.get("SITE_PASSPHRASE", "")
    if len(mdp) < 12:
        sys.exit("SITE_PASSPHRASE absent ou trop court (12 caractères minimum) : voir le README.")
    src, dst = sys.argv[1:3]
    json.dump(chiffrer(open(src, "rb").read(), mdp), open(dst, "w"), separators=(",", ":"))
    print("fichier chiffré écrit :", dst)
