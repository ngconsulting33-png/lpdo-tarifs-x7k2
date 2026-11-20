#!/usr/bin/env python3
"""Extrait les règles de calcul des classeurs Excel (formules) vers un fichier JSON.

Usage:
    python3 tools/build_rules_from_xlsx.py Achat_Vente_pièces.xlsx Tarif_achat_Bijoux.xlsx config/rules.private.json

Le JSON produit contient tes coefficients, commissions et tranches : il ne doit
JAMAIS être commité dans un dépôt public (il est dans .gitignore). On le colle
dans le secret GitHub RULES_JSON.
"""
import json
import re
import sys

import openpyxl


# Seuils (en euros) à partir desquels chaque tranche s'applique, dans l'ordre des colonnes
# du fichier. None = tranche sans montant dans le fichier (jamais choisie automatiquement).
MIN_ARGENT_RACHAT = [5000, 3000, 1000, 500, 0]
MIN_ARGENT_VENTE = [5000, 3000, 1000, 500, 0]
MIN_OR = [None, 100000, 50000, 25000, 10000, 5000, 1000, 0]


def with_min(tiers, mins):
    for t, m in zip(tiers, mins):
        t["min_eur"] = m
    return tiers


GRID_COLS = ["B", "D", "F", "H", "J", "L", "N", "P", "R", "T", "V"]  # colonnes de prix de la grille


def load(path, data_only=False):
    return openpyxl.load_workbook(path, data_only=data_only)


def cot_label(wb_vals, cell_ref):
    """'Cours de Bourse'!B30 -> libellé de la ligne 30."""
    row = int(re.search(r"(\d+)$", cell_ref).group(1))
    return wb_vals["Cours de Bourse"].cell(row, 1).value.strip()


def silver_rows(ws, wv, first, last, wb_vals):
    rows = []
    for r in range(first, last + 1):
        label = ws.cell(r, 1).value
        poids = ws.cell(r, 2).value
        titre = ws.cell(r, 3).value
        dform = ws.cell(r, 4).value
        if not label or not isinstance(poids, (int, float)) or not isinstance(dform, str):
            continue
        item = {"name": label.strip(), "poids": poids, "titre": titre, "row": r}
        m = re.search(r"'Cours de Bourse'!(B\d+)", dform)
        if m:
            item["kind"] = "cotation"
            item["cot_key"] = cot_label(wb_vals, m.group(1))
        else:
            m2 = re.search(r"\(\$A\$2\+(\d+)\)", dform)
            if m2:
                item["kind"] = "lingot"
                item["prime_eur_kg"] = int(m2.group(1))
            else:
                item["kind"] = "spot"
        rows.append(item)
    return rows


def main(coins_xlsx, bijoux_xlsx, out):
    wb = load(coins_xlsx)
    wv = load(coins_xlsx, True)
    rules = {"_note": "PRIVÉ - ne pas publier. Généré depuis les classeurs Excel."}

    # ---------- RACHAT ARGENT ----------
    ws = wb["RACHAT Pièces ARGENT"]
    tier_cols = ["F", "J", "N", "R", "V"]
    tiers = []
    for col in tier_cols:
        c = openpyxl.utils.column_index_from_string(col)
        tiers.append({"commission": ws.cell(5, c).value, "label": str(ws.cell(6, c).value)})
    with_min(tiers, MIN_ARGENT_RACHAT)
    rows = silver_rows(ws, wv["RACHAT Pièces ARGENT"], 7, 40, wv)
    for it in rows:
        # CORRECTION : dans le fichier, "Kookabura 1 kg" pointe sur la case du 100 F argent
        # ('Cours de Bourse'!B45) au lieu de la sienne (B46).
        if it["name"].lower().startswith("kookabura 1 kg") and it.get("cot_key") == "100 fr Argent":
            it["cot_key"] = wv["Cours de Bourse"]["A46"].value.strip()
            it["correction"] = "référence corrigée B45 -> B46"
            print("Correction appliquée :", it["name"], "->", it["cot_key"])
        # frais : colonne E - section non boursable (E5=10%) ; boursable (E12 vide)
        it["frais"] = ws["E5"].value if it["row"] < 11 else 0.0
    rules["argent_rachat"] = {
        "tmp": ws["H5"].value,
        "tiers": tiers,
        "rows": rows,
    }

    # ---------- VENTE ARGENT ----------
    ws = wb["VENTE Pièces ARGENT"]
    tcols = ["E", "G", "I", "K", "M"]
    tiers = []
    for col in tcols:
        c = openpyxl.utils.column_index_from_string(col)
        tiers.append({"commission": ws.cell(4, c).value, "label": str(ws.cell(5, c).value)})
    with_min(tiers, MIN_ARGENT_VENTE)
    rows = silver_rows(ws, wv["VENTE Pièces ARGENT"], 7, 40, wv)
    rules["argent_vente"] = {"tiers": tiers, "rows": rows}

    # ---------- RACHAT OR ----------
    ws = wb["RACHAT Pièces OR"]
    tier_cols = ["F", "J", "N", "R", "V", "Z", "AD", "AH"]
    tiers = []
    for col in tier_cols:
        c = openpyxl.utils.column_index_from_string(col)
        lab = ws.cell(6, c).value
        tiers.append({"commission": ws.cell(5, c).value, "label": str(lab) if lab else None})
    with_min(tiers, MIN_OR)
    rows = []
    for r in range(8, 49):
        label = ws.cell(r, 1).value
        poids, titre = ws.cell(r, 2).value, ws.cell(r, 3).value
        if not label or not isinstance(poids, (int, float)):
            continue
        frais = ws["E5"].value if ws.cell(r, 5).value else 0.0
        rows.append({"name": label.strip(), "poids": poids, "titre": titre, "frais_fonte": frais, "row": r})
    rules["or_rachat"] = {
        "tmp": ws["H5"].value,
        "cours_offset_eur_kg": int(re.search(r"-\s*(\d+)", wb["RACHAT Pièces OR"]["A2"].value).group(1)) * -1,
        "tiers": tiers,
        "rows": rows,
    }

    # ---------- VENTE OR ----------
    ws = wb["VENTE Pièces OR"]
    tier_cols = ["E", "G", "I", "K", "M", "O", "Q", "S"]
    tiers = []
    for col in tier_cols:
        c = openpyxl.utils.column_index_from_string(col)
        lab = ws.cell(6, c).value
        tiers.append({"commission": ws.cell(5, c).value, "label": str(lab) if lab else None})
    with_min(tiers, MIN_OR)
    rows = []
    for r in range(7, 48):
        label = ws.cell(r, 1).value
        poids, titre = ws.cell(r, 2).value, ws.cell(r, 3).value
        if not label or not isinstance(poids, (int, float)):
            continue
        dform = ws.cell(r, 4).value
        m = re.search(r"\*(\d\.\d+)$", dform)
        rows.append({"name": label.strip(), "poids": poids, "titre": titre,
                     "multiplicateur": float(m.group(1)) if m else 1.0, "row": r})
    rules["or_vente"] = {
        "cours_offset_eur_kg": int(re.search(r"\+\s*(\d+)", wb["VENTE Pièces OR"]["A2"].value).group(1)),
        "tiers": tiers,
        "rows": rows,
    }

    # ---------- BIJOUX ----------
    wbj = load(bijoux_xlsx)
    ws = wbj["Rachat Bijoux BASE"]
    bij = []
    for c in range(5, 16):
        head = ws.cell(1, c).value
        form = ws.cell(2, c).value
        if not head or not form:
            continue
        # =ROUNDUP(((B3*0.75*0.68)/1000)*0.8,0)  ou  =((B4*0.925*0.5)/1000)
        metal = "or" if form.count("B2") or form.count("B3") else "argent"
        coefs = [float(x) for x in re.findall(r"\*(\d*\.\d+)", form)]
        rounding = "up" if "ROUNDUP" in form else ("down" if "ROUNDDOWN" in form else None)
        titre = coefs[0]
        coef = 1.0
        for x in coefs[1:]:
            coef *= x
        # --- revente à la fonte (ligne 3) : produit de tous les coefficients de la formule
        rev = 1.0
        for x in re.findall(r"\*(\d*\.\d+)", ws.cell(3, c).value):
            rev *= float(x)
        # --- grille de prix possibles (lignes 14, 18, 22... dans la colonne de prix correspondante)
        grid_col = GRID_COLS[len(bij)]
        steps = [r for r in range(14, 246) if ws[f"A{r}"].value == "CA" and ws[f"{grid_col}{r}"].value is not None]
        incr = [float(re.search(r"\+(\d*\.?\d+)$", ws[f"{grid_col}{r}"].value).group(1)) for r in steps[1:]]
        bij.append({"col": openpyxl.utils.get_column_letter(c), "label": head, "metal": metal,
                    "blanc_rose": c in (10, 11, 12), "titre": titre, "coef": round(coef, 6),
                    "rounding": rounding, "revente_coef": round(rev, 6),
                    "valo_mult": 0.9 if c in (10, 11, 12) else 1.0,
                    "incrementation": incr, "formule_excel": form})
    marge_coef = float(re.search(r"\*(\d*\.\d+)$", ws["C16"].value).group(1))
    rules["bijoux"] = {"colonnes": bij, "marge_coef": marge_coef}

    json.dump(rules, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("règles écrites dans", out)
    for k in ("argent_rachat", "argent_vente", "or_rachat", "or_vente"):
        print(k, len(rules[k]["rows"]), "lignes,", len(rules[k]["tiers"]), "tranches")
    print("bijoux:", [(b["label"], b["titre"], b["coef"], b["rounding"]) for b in bij])


if __name__ == "__main__":
    main(*sys.argv[1:4])
