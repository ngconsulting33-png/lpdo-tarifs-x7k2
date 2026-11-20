#!/usr/bin/env python3
"""Vérifie que le moteur Python redonne les mêmes chiffres que tes classeurs Excel.

Usage: python3 tools/test_against_xlsx.py coins.xlsx bijoux.xlsx config/rules.private.json
Les écarts attendus (anomalies connues du fichier) sont listés à part.
"""
import json
import os
import sys

import openpyxl
from openpyxl.utils import column_index_from_string as ci

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import engine  # noqa: E402

coins_xlsx, bijoux_xlsx, rules_path = sys.argv[1:4]
rules = json.load(open(rules_path, encoding="utf-8"))
wv = openpyxl.load_workbook(coins_xlsx, data_only=True)
cb = wv["Cours de Bourse"]
cotations = {}
for r in range(30, 47):
    if cb.cell(r, 1).value and isinstance(cb.cell(r, 2).value, (int, float)):
        cotations[cb.cell(r, 1).value.strip()] = cb.cell(r, 2).value
spot_ag, spot_or = cb["B49"].value, cb["B50"].value

checked = 0
mismatch = []


def cmp(label, got, expect, tol=0.006):
    global checked
    if expect is None or got is None:
        return
    checked += 1
    if abs(got - expect) > tol:
        mismatch.append((label, round(got, 4), round(expect, 4)))


def check_rachat(sheet, rows, res, first_cols):
    """Compare commission, valeur, TMP et net de chaque tranche (colonnes F,G,H,I puis J,K,L,M...)."""
    ws = wv[sheet]
    for item, row in zip(res, rows):
        cmp(f"{sheet} | {row['name']} | brut", item["brut"], ws.cell(row["row"], 4).value)
        for i, col in enumerate(first_cols):
            c = ci(col)
            t = item["tiers"][i]
            if t is None:
                continue
            for k, (cle, off, signe) in enumerate((("commission", 0, -1), ("valeur", 1, 1), ("tmp", 2, -1), ("net", 3, 1))):
                cmp(f"{sheet} | {row['name']} | tranche {i + 1} {cle}", signe * t[cle],
                    ws.cell(row["row"], c + off).value)


def check_vente(sheet, rows, res, first_cols):
    ws = wv[sheet]
    for item, row in zip(res, rows):
        cmp(f"{sheet} | {row['name']} | brut", item["brut"], ws.cell(row["row"], 4).value)
        for i, col in enumerate(first_cols):
            t = item["tiers"][i]
            if t is None:
                continue
            cmp(f"{sheet} | {row['name']} | tranche {i + 1} commission", t["commission"], ws.cell(row["row"], ci(col)).value)
            cmp(f"{sheet} | {row['name']} | tranche {i + 1} prix", t["prix"], ws.cell(row["row"], ci(col) + 1).value)


R_ARG = engine.argent_rachat(rules, spot_ag, cotations)
check_rachat("RACHAT Pièces ARGENT", rules["argent_rachat"]["rows"], R_ARG, ["F", "J", "N", "R", "V"])
check_vente("VENTE Pièces ARGENT", rules["argent_vente"]["rows"], engine.argent_vente(rules, spot_ag, cotations),
            ["E", "G", "I", "K", "M"])
check_rachat("RACHAT Pièces OR", rules["or_rachat"]["rows"], engine.or_rachat(rules, spot_or),
             ["F", "J", "N", "R", "V", "Z", "AD", "AH"])
check_vente("VENTE Pièces OR", rules["or_vente"]["rows"], engine.or_vente(rules, spot_or),
            ["E", "G", "I", "K", "M", "O", "Q", "S"])

bj = openpyxl.load_workbook(bijoux_xlsx, data_only=True)["Rachat Bijoux BASE"]
res = engine.bijoux(rules, bj["B2"].value, bj["B4"].value)
GRID = ["B", "D", "F", "H", "J", "L", "N", "P", "R", "T", "V"]
mc = rules["bijoux"]["marge_coef"]
for col, item, g in zip(rules["bijoux"]["colonnes"], res, GRID):
    nom = f"Bijoux | {col['label']}{' blanc/rose' if col['blanc_rose'] else ''}"
    L = col["col"]
    cmp(nom + " net", item["net_gramme"], bj[f"{L}2"].value, tol=1e-6)
    cmp(nom + " revente fonte", item["revente_g"], bj[f"{L}3"].value, tol=1e-6)
    cmp(nom + " marge/g", item["marge_g"], bj[f"{L}4"].value, tol=1e-6)
    cmp(nom + " taux marge", item["taux_marge"], bj[f"{L}5"].value, tol=1e-6)
    cmp(nom + " valo gramme brut", item["valeur_gramme"], bj[f"{L}6"].value, tol=1e-6)
    # grille des prix possibles, poids = 1 g (cellule B8)
    pc = ci(g)
    for k, prix in enumerate(item["prix"]):
        r = 14 + 4 * k
        cmp(nom + f" grille {k} prix", prix, bj.cell(r, pc).value, tol=1e-6)
        rev, ach = item["revente_g"], prix
        cmp(nom + f" grille {k} MB", (rev - ach) * mc, bj.cell(r + 2, pc + 1).value, tol=1e-6)
        cmp(nom + f" grille {k} %", (rev - ach) * mc / ach, bj.cell(r + 3, pc + 1).value, tol=1e-6)

print(f"{checked} valeurs comparées, {len(mismatch)} écart(s).")
import collections
groupes = collections.Counter()
for m in mismatch:
    groupes[" | ".join(m[0].split(" | ")[:2]) if "tranche 1" not in m[0] else m[0].split(" | ")[0] + " (tranche 2 %)"] += 1
for m in mismatch:
    print("  ÉCART", m[0], "moteur =", m[1], "Excel =", m[2])
