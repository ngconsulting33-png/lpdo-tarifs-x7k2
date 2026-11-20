#!/usr/bin/env python3
"""Teste les analyseurs de pages sur des extraits réels (copiés des pages le 20/11/2026)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import sources as S  # noqa: E402

# --- BullionVault argent (tableau lu sur la page)
txt = """Prix de l'argent par gramme\t1,24 €\t1,36 $\t1,04 £
Prix de l'argent par kilo\t1 240,00 €\t1 361,00 $\t1 038,00 £
SPrix de l'argent par once\t38,57 €\t42,33 $\t32,29 £
20 novembre 2026, 08:18:03 (GMT+00:00)
Cours Actuel 1 244,61 €/kg"""
kg, when = S.parse_bullionvault(txt)
assert kg == 1240.0, kg
assert when.startswith("20 novembre 2026, 08:18:03"), when

# BullionVault or (valeurs de la page du 20/11/2026) + repli sur l'once
kg, _ = S.parse_bullionvault("Prix de l'or par kilo 103 339 € 113 000 $")
assert kg == 103339.0, kg
kg, _ = S.parse_bullionvault("Prix de l'or par once 3 214,20 €")
assert abs(kg - 103339.6) < 5, kg

# --- Godot bijoux : texte collé par Nicolas
godot = """CARAT\tQUANTITÉ (g)\tPRIX/GRAMME\tTOTAL ESTIMÉ
24 carats
0
99.73 €\t0 €
22 carats
0
87.57 €\t0 €
18 carats
0
69.68 €\t0 €
14 carats
0
50.83 €\t0 €
9 carats
0
32.28 €\t0 €
Pièces Argent
0
1.0085 €"""
r = S.parse_godot_bijoux(godot)
assert r == {"24K": 99.73, "22K": 87.57, "18K": 69.68, "14K": 50.83, "9K": 32.28, "argent_pieces_g": 1.0085}, r

# --- Godot argent (tableau HTML)
html = """<table><tr><th>Produit</th><th>Valeur intrinsèque</th><th>Prime</th><th>Achat</th><th>Vente</th></tr>
<tr><td>Maple Leaf 1 Once Argent</td><td>38.14 €</td><td>21.39 %</td><td>46.30 €</td><td>35.80 €</td><td><a href="/x">voir</a></td></tr>
<tr><td>50 Francs Hercule 1974-1980</td><td>33.11 €</td><td>13.25 %</td><td>37.50 €</td><td>28.10 €</td></tr>
<tr><td>Lingot 1 Kilo Argent</td><td>1 226.27 €</td><td>31.01 %</td><td>1 606.50 €</td><td>1 128.10 €</td></tr></table>"""
r = S.parse_godot_argent(html)
assert r["maple leaf 1 once argent"]["vente"] == 35.80
assert r["50 francs hercule 1974 1980"]["achat"] == 37.50
assert r["lingot 1 kilo argent"]["vente"] == 1128.10, r["lingot 1 kilo argent"]

# --- gold.fr
html = """<table><tr><td>Maple Leaf 1 oz</td><td>47,66 €</td><td>22,5 %</td></tr>
<tr><td>Koala Argent 1 kg 2025-2026</td><td>1 574,56 €</td><td>26,0 %</td></tr>
<tr><td>5 Francs Hercule (Écu)</td><td>33,77 €</td><td>20,0 %</td></tr></table>"""
r = S.parse_goldfr(html)
assert r["maple leaf 1 oz"]["prix"] == 47.66
assert r["koala argent 1 kg 2025 2026"]["prix"] == 1574.56
assert r["5 francs hercule ecu"]["prime"] == 20.0

# --- Fidso fiche produit
fidso = """50 Francs Hercule Argent
Valeur métal\n33,49 €\nCours FR\n36,84 €\nPrime 10 %\nVendre HT\n24,78 €\nAcheter TTC\n42,86 €"""
r = S.parse_fidso_produit(fidso)
assert r == {"vendre_ht": 24.78, "acheter_ttc": 42.86, "cours_fr": 36.84}, r

print("Tous les analyseurs passent sur les exemples.")
