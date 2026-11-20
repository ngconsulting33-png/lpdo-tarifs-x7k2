"""Moteur de calcul des tarifs, fidèle aux formules des classeurs Excel.

Toutes les fonctions sont pures : elles prennent les règles (JSON privé), les cours
et les cotations, et renvoient des listes de dictionnaires. Aucune dépendance externe.
"""
import math


def _floor(x):
    return math.floor(round(x, 9))


def _ceil(x):
    return math.ceil(round(x, 9))


def _valeur_argent(row, spot_ag_kg, cotations):
    """Valeur 'cours' (colonne D) d'une ligne de pièce/lingot argent."""
    if row["kind"] == "cotation":
        v = cotations.get(row["cot_key"])
        return None if v is None else float(v)
    cours = spot_ag_kg + row.get("prime_eur_kg", 0)
    return row["poids"] * row["titre"] * cours / 1000.0


def argent_rachat(rules, spot_ag_kg, cotations):
    cfg = rules["argent_rachat"]
    out = []
    for row in cfg["rows"]:
        d = _valeur_argent(row, spot_ag_kg, cotations)
        item = {"name": row["name"], "poids": row["poids"], "titre": row["titre"],
                "valeur_brute": None if d is None else round(d, 4),
                "brut": None if d is None else d,
                "frais": None if d is None else d * row["frais"], "nets": [], "tiers": []}
        for t in cfg["tiers"]:
            if d is None:
                item["nets"].append(None)
                item["tiers"].append(None)
                continue
            comm = d * t["commission"]
            valeur = d - d * row["frais"] - comm
            tmp = valeur * cfg["tmp"]
            net = valeur - tmp
            item["nets"].append(round(net, 4))
            item["tiers"].append({"commission": comm, "valeur": valeur, "tmp": tmp, "net": net})
        out.append(item)
    return out


def argent_vente(rules, spot_ag_kg, cotations):
    cfg = rules["argent_vente"]
    out = []
    for row in cfg["rows"]:
        d = _valeur_argent(row, spot_ag_kg, cotations)
        item = {"name": row["name"], "poids": row["poids"], "titre": row["titre"],
                "valeur_brute": None if d is None else round(d, 4),
                "brut": None if d is None else d, "prix": [], "tiers": []}
        for t in cfg["tiers"]:
            if d is None:
                item["prix"].append(None)
                item["tiers"].append(None)
                continue
            item["prix"].append(round(d * (1 + t["commission"]), 4))
            item["tiers"].append({"commission": d * t["commission"], "prix": d * (1 + t["commission"])})
        out.append(item)
    return out


def or_rachat(rules, spot_or_kg):
    cfg = rules["or_rachat"]
    cours = spot_or_kg + cfg["cours_offset_eur_kg"]
    out = []
    for row in cfg["rows"]:
        d = row["poids"] * row["titre"] * cours / 1000.0
        item = {"name": row["name"], "poids": row["poids"], "titre": row["titre"],
                "valeur_brute": round(d, 4), "brut": d, "frais": d * row["frais_fonte"],
                "nets": [], "tiers": []}
        for t in cfg["tiers"]:
            comm = d * t["commission"]
            tmp = (d - comm) * cfg["tmp"]
            frais = d * row["frais_fonte"]
            net = _floor(d - tmp - frais - comm)
            item["nets"].append(net)
            item["tiers"].append({"commission": comm, "valeur": d - frais - comm, "tmp": tmp, "net": net})
        out.append(item)
    return out


def or_vente(rules, spot_or_kg):
    cfg = rules["or_vente"]
    cours = spot_or_kg + cfg["cours_offset_eur_kg"]
    out = []
    for row in cfg["rows"]:
        d = row["poids"] * row["titre"] * cours / 1000.0 * row["multiplicateur"]
        item = {"name": row["name"], "poids": row["poids"], "titre": row["titre"],
                "valeur_brute": round(d, 4), "brut": d, "prix": [], "tiers": []}
        for t in cfg["tiers"]:
            p = _ceil(d * (1 + t["commission"]))
            item["prix"].append(p)
            item["tiers"].append({"commission": d * t["commission"], "prix": p})
        out.append(item)
    return out


def _grille(depart, incr):
    prix, p = [round(depart, 4)], depart
    for x in incr:
        p += x
        prix.append(round(p, 4))
    return prix


def bijoux(rules, spot_or_kg, spot_ag_kg, offset_argent_kg=0.0):
    """Rachat bijoux : prix net au gramme, revente à la fonte, marge et prix possibles."""
    out = []
    for col in rules["bijoux"]["colonnes"]:
        spot = spot_or_kg if col["metal"] == "or" else spot_ag_kg + offset_argent_kg
        v = spot * col["titre"] * col["coef"] / 1000.0
        if col["rounding"] == "up":
            v = _ceil(v)
        elif col["rounding"] == "down":
            v = _floor(v)
        revente = spot * col["revente_coef"] / 1000.0
        valo = spot * col["titre"] * col["valo_mult"] / 1000.0
        out.append({
            "label": col["label"], "metal": col["metal"], "blanc_rose": col["blanc_rose"],
            "titre": col["titre"], "net_gramme": v, "revente_g": revente,
            "marge_g": revente - v, "taux_marge": (revente - v) / revente,
            "valeur_gramme": valo,
            "prix": _grille(v, col["incrementation"]),
        })
    return out


def choisir_tranche(tiers, montant):
    """Indice de la tranche applicable à un montant (None si aucune)."""
    best = None
    for i, t in enumerate(tiers):
        m = t.get("min_eur")
        if m is None:
            continue
        if montant >= m and (best is None or m > tiers[best]["min_eur"]):
            best = i
    return best
