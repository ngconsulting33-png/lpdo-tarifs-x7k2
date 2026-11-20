#!/usr/bin/env python3
"""Calcule data/prices.json : cours, tarifs LPDO et comparatif concurrents.

Usage (dans GitHub Actions) :  python3 scripts/build_prices.py --out _site/data/prices.json
Usage (essai sans internet) :  python3 scripts/build_prices.py --demo --out /tmp/prices.json

Les règles (coefficients, commissions) sont lues dans config/rules.private.json,
écrit par le workflow à partir du secret GitHub RULES_JSON. Le fichier produit ne
contient que des RÉSULTATS (prix nets par tranche), jamais les coefficients.
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import engine  # noqa: E402
import sources as S  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")

# libellé de la ligne dans 'Cours de Bourse' -> nom sur gold.fr
GOLDFR = {
    "Maple leaf 1 oz": "Maple Leaf 1 oz",
    "Vienna Philharmonic 1 oz": "Vienna Philharmonic 1 oz",
    "Kangourou / Koala / Kookabura 1 oz": "Kangourou 1 oz",
    "Britannia 1 oz": "Britannia 1 oz",
    "American Eagle 1oz": "American Eagle 1 oz",
    "Krugerrand 1 oz": "Krugerrand Argent 1 oz",
    "China Panda": "China Panda 30 g",
    "Koala 1 kg": "Koala Argent 1 kg",
    "Libertad Mexicaine": "American Eagle 1 oz",  # dans le fichier : B38 = B34
    "20 Fr Turin": "20 Francs Turin",
    "50 Fr Hercule": "50 Francs Hercule",
    "5 Fr Semeuse": "5 Francs Semeuse",
    "10 Fr Hercule": "10 Francs Hercule",
    "10 Fr Turin": "10 Francs Turin",
    "5 Fr Hercule ou ECU": "5 Francs Hercule",
    "100 fr Argent": "100 Francs en Argent",
    "Kookabura 1 Kg": "Kookaburra 1 kg",
}

# ligne LPDO -> nom chez Godot (achat-or-et-argent.fr)
GODOT = {
    "Maple leaf 1 oz": "Maple Leaf 1 Once Argent",
    "Krugerrand 1 oz": "Krugerrand 1 Once Argent",
    "American Eagle 1oz": "Silver Eagle 1 Once",
    "50 Fr Hercule": "50 Francs Hercule 1974 1980",
    "10 Fr Hercule": "10 Francs Hercule 1964 1973",
    "5 Fr Semeuse": "5 Francs Semeuse 1959 1969",
    "Lingot 1 kg": "Lingot 1 Kilo Argent",
    "Lingotin 500 g": "Lingot 500g Argent",
    "Lingotin 250 g": "Lingot 250g Argent",
}

# ligne LPDO -> page produit Fidso Arcachon
FIDSO = {
    "Maple leaf 1 oz": ("pieces-argent", "maple-leaf-1-oz"),
    "Vienna Philharmonic 1 oz": ("pieces-argent", "vienna-philharmonique-1-oz"),
    "Kangourou / Koala / Kookabura 1 oz": ("pieces-argent", "kangourou-1-oz"),
    "Britannia 1 oz": ("pieces-argent", "britannia-1-oz"),
    "American Eagle 1oz": ("pieces-argent", "american-silver-eagle-1-oz"),
    "Krugerrand 1 oz": ("pieces-argent", "krugerrand-1-oz"),
    "China Panda": ("pieces-argent", "panda-30-g"),
    "50 Fr Hercule": ("pieces-argent", "50-francs-hercule"),
    "10 Fr Hercule": ("pieces-argent", "10-francs-hercule"),
    "5 Fr Hercule ou ECU": ("pieces-argent", "5-francs-ecu"),
    "5 Fr Semeuse": ("pieces-argent", "5-francs-semeuse"),
    "Lingot 1 kg": ("lingots-argent", "lingot-1-kg-fidji"),
    "Lingotin 500 g": ("lingots-argent", "lingotin-500-g-fidji"),
    "Lingotin 250 g": ("lingots-argent", "lingotin-250-g-fidji"),
    "Lingotin 100 g": ("lingots-argent", "lingotin-100-g-fidji"),
    "Lingotin 1 oz": ("lingots-argent", "lingotin-1-oz-fidji"),
}

# Données d'exemple (relevées le 20/11/2026) pour l'essai --demo
DEMO = {
    "spot": {"or_kg": 103339.0, "ag_kg": 1240.0, "heure": "20 novembre 2026, 08:18 (GMT)"},
    "goldfr": {
        "Maple Leaf 1 oz": 47.66, "Vienna Philharmonic 1 oz": 47.42, "Kangourou 1 oz": 46.30,
        "Britannia 1 oz": 47.42, "American Eagle 1 oz": 49.36, "Krugerrand Argent 1 oz": 47.42,
        "China Panda 30 g": 52.11, "Koala Argent 1 kg": 1574.56, "20 Francs Turin": 19.05,
        "50 Francs Hercule": 37.49, "5 Francs Semeuse": 13.79, "10 Francs Hercule": 31.24,
        "10 Francs Turin": 9.53, "5 Francs Hercule": 33.77, "100 Francs en Argent": 18.58,
        "Kookaburra 1 kg": 1550.96},
    "godot_argent": {
        "Maple Leaf 1 Once Argent": (46.30, 35.80), "Krugerrand 1 Once Argent": (46.30, 35.80),
        "Silver Eagle 1 Once": (48.40, 35.80), "50 Francs Hercule 1974 1980": (37.50, 28.10),
        "10 Francs Hercule 1964 1973": (31.20, 23.40), "5 Francs Semeuse 1959 1969": (14.80, 10.40),
        "Lingot 1 Kilo Argent": (1606.50, 1128.10), "Lingot 500g Argent": (809.40, 564.00),
        "Lingot 250g Argent": (410.80, 282.00)},
    "godot_bijoux": {"24K": 99.73, "22K": 87.57, "18K": 69.68, "14K": 50.83, "9K": 32.28,
                     "argent_pieces_g": 1.0085},
    "fidso": {"50 Fr Hercule": 24.78},
}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def lire_json(path, defaut=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return defaut


def lire_sources(demo, manual):
    """Renvoie un dict de données brutes + une liste d'états par source."""
    etats, data = [], {}

    def etat(id_, ok, msg=""):
        etats.append({"id": id_, "ok": ok, "message": msg, "heure": now()})

    if demo:
        data.update(spot=DEMO["spot"], goldfr=DEMO["goldfr"], godot_argent={
            S.norm(k): {"achat": v[0], "vente": v[1]} for k, v in DEMO["godot_argent"].items()},
            godot_bijoux=DEMO["godot_bijoux"], fidso={k: {"vendre_ht": v} for k, v in DEMO["fidso"].items()})
        etat("demo", True, "Données d'exemple (mode --demo)")
        return data, etats

    with S.Navigateur() as nav:
        # --- cours BullionVault
        spot = {}
        for cle, url, motif in (("or_kg", S.URL_OR, r"par\s+kilo"), ("ag_kg", S.URL_ARGENT, r"par\s+kilo")):
            try:
                _, texte = nav.page(url, attendre_texte=motif)
                kg, heure = S.parse_bullionvault(texte)
                if kg is None:
                    raise ValueError("prix au kilo introuvable")
                spot[cle] = kg
                spot["heure_" + cle] = heure
                etat("bullionvault_" + cle, True, f"{kg:.2f} €/kg")
            except Exception as e:  # noqa: BLE001
                etat("bullionvault_" + cle, False, str(e)[:200])
        data["spot"] = spot

        # --- cotations gold.fr
        try:
            try:
                html, _ = nav.page(S.URL_GOLDFR, attendre_texte=r"Maple")
            except Exception as e1:  # une seconde tentative, sans attente de texte
                html, txt = nav.page(S.URL_GOLDFR, timeout=45000)
                if "Maple" not in html:
                    raise ValueError(f"page reçue sans tableau ({len(html)} octets) : {txt[:120]!r} / 1re erreur : {str(e1)[:80]}")
            gf = S.parse_goldfr(html)
            if len(gf) < 5:
                raise ValueError(f"seulement {len(gf)} lignes lues")
            data["goldfr"] = {v["nom"]: v["prix"] for v in gf.values()}
            etat("goldfr", True, f"{len(gf)} produits")
        except Exception as e:  # noqa: BLE001
            etat("goldfr", False, str(e)[:200])

        # --- Godot : pièces et lingots argent
        try:
            html, _ = nav.page(S.URL_GODOT_ARGENT, attendre_texte=r"Maple Leaf")
            ga = S.parse_godot_argent(html)
            if len(ga) < 3:
                raise ValueError(f"seulement {len(ga)} lignes lues")
            data["godot_argent"] = ga
            etat("godot_argent", True, f"{len(ga)} produits")
        except Exception as e:  # noqa: BLE001
            etat("godot_argent", False, str(e)[:200])

        # --- Godot : bijoux
        try:
            _, texte = nav.page(S.URL_GODOT_BIJOUX, attendre_texte=r"24 carats[\s\S]{0,40}\d+[.,]\d+\s*€")
            gb = S.parse_godot_bijoux(texte)
            if len(gb) < 5:
                raise ValueError(f"seulement {len(gb)} valeurs lues")
            data["godot_bijoux"] = gb
            etat("godot_bijoux", True, f"{len(gb)} valeurs")
        except Exception as e:  # noqa: BLE001
            etat("godot_bijoux", False, str(e)[:200])

        # --- Fidso Arcachon : une fiche par produit
        fid, ok_n = {}, 0
        for nom, (cat, slug) in FIDSO.items():
            try:
                _, texte = nav.page(S.URL_FIDSO.format(cat=cat, slug=slug), attendre_texte=r"Vendre\s*HT")
                r = S.parse_fidso_produit(texte)
                if "vendre_ht" in r:
                    fid[nom] = r
                    ok_n += 1
            except Exception:  # noqa: BLE001
                pass
        data["fidso"] = fid
        etat("fidso_pieces", ok_n > 0, f"{ok_n}/{len(FIDSO)} fiches lues")
    return data, etats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--rules", default=os.path.join(ROOT, "config", "rules.private.json"))
    ap.add_argument("--manual", default=os.path.join(ROOT, "data", "manual.json"))
    ap.add_argument("--demo", action="store_true", help="données d'exemple, sans internet")
    a = ap.parse_args()

    rules = lire_json(a.rules)
    if not rules:
        sys.exit("Règles introuvables : le secret RULES_JSON est-il créé ? (voir README)")
    manual = lire_json(a.manual, {})
    data, etats = lire_sources(a.demo, manual)

    # ---- cours (repli manuel si la lecture échoue)
    spot = data.get("spot", {})
    ov = manual.get("spot_override", {}) or {}
    or_kg = ov.get("or_kg") or spot.get("or_kg")
    ag_kg = ov.get("ag_kg") or spot.get("ag_kg")
    if not (50000 < (or_kg or 0) < 250000 and 300 < (ag_kg or 0) < 8000):
        sys.exit(f"Cours inutilisables (or={or_kg}, argent={ag_kg}) : publication annulée, "
                 "l'ancienne version du site reste en ligne.")

    # ---- cotations argent boursable (gold.fr), repli manuel
    goldfr = {S.norm(k): v for k, v in (data.get("goldfr") or {}).items()}
    cot = {}
    labels = {r["cot_key"] for k in ("argent_rachat", "argent_vente") for r in rules[k]["rows"]
              if r["kind"] == "cotation"}
    for lab in labels:
        want = S.norm(GOLDFR.get(lab, lab))
        val = next((v for k, v in goldfr.items() if k == want or k.startswith(want + " ")), None)
        val = (manual.get("cotations_override") or {}).get(lab) or val
        if val is not None:
            cot[lab] = val

    # ---- calculs LPDO
    off_ag = rules.get("bijoux_argent_offset_eur_kg", 0.0)
    res = {
        "argent_rachat": engine.argent_rachat(rules, ag_kg, cot),
        "argent_vente": engine.argent_vente(rules, ag_kg, cot),
        "or_rachat": engine.or_rachat(rules, or_kg),
        "or_vente": engine.or_vente(rules, or_kg),
        "bijoux": engine.bijoux(rules, or_kg, ag_kg, off_ag),
    }

    def r4(v):
        return None if v is None else round(v, 4)

    def publics(key):
        cfg = rules[key]
        achat = key.endswith("rachat")
        tiers = [{"label": t["label"], "commission": t["commission"], "min_eur": t.get("min_eur")}
                 for t in cfg["tiers"]]
        rows = []
        for src, calc in zip(cfg["rows"], res[key]):
            ligne = {"name": calc["name"], "poids": calc["poids"], "titre": calc["titre"],
                     "brut": r4(calc["brut"]),
                     "section": {"spot": "Argent non boursable", "cotation": "Argent boursable (cotations gold.fr)",
                                 "lingot": "Lingots et lingotins (cours + prime)"}.get(src.get("kind"))}
            if achat:
                ligne["frais"] = r4(calc["frais"])
                ligne["frais_pct"] = src.get("frais", src.get("frais_fonte", 0.0))
                ligne["tiers"] = [None if t is None else {k: r4(v) for k, v in t.items()}
                                  for t in calc["tiers"]]
            else:
                ligne["tiers"] = [None if t is None else {k: r4(v) for k, v in t.items()}
                                  for t in calc["tiers"]]
            rows.append(ligne)
        return {"tiers": tiers, "rows": rows}

    tmp = rules["argent_rachat"]["tmp"]
    out = {
        "genere_le": now(),
        "demo": bool(a.demo),
        "tmp": tmp,
        "spot": {"or_kg": or_kg, "ag_kg": ag_kg,
                 "or_g": round(or_kg / 1000, 2), "ag_g": round(ag_kg / 1000, 4),
                 "heure_or": spot.get("heure_or_kg") or spot.get("heure"),
                 "heure_ag": spot.get("heure_ag_kg") or spot.get("heure"),
                 "manuel": bool(ov.get("or_kg") or ov.get("ag_kg"))},
        "cours_utilises": {
            "argent": ag_kg,
            "or_rachat": or_kg + rules["or_rachat"]["cours_offset_eur_kg"],
            "or_vente": or_kg + rules["or_vente"]["cours_offset_eur_kg"]},
        "argent_rachat": publics("argent_rachat"),
        "argent_vente": publics("argent_vente"),
        "or_rachat": publics("or_rachat"),
        "or_vente": publics("or_vente"),
        "bijoux": {"marge_coef": rules["bijoux"]["marge_coef"],
                   "lignes": [{k: (r4(v) if isinstance(v, float) else v) for k, v in b.items() if k != "prix"}
                              | {"prix": [r4(x) for x in b["prix"]]} for b in res["bijoux"]]},
        "cotations": cot,
    }

    # ---- comparatif concurrents
    ga, fid = data.get("godot_argent") or {}, data.get("fidso") or {}
    comp = []
    for row in out["argent_rachat"]["rows"]:
        n = row["name"]
        g = ga.get(S.norm(GODOT[n])) if n in GODOT else None
        f = fid.get(n)
        if not (g or f):
            continue
        item = {"name": n, "lpdo": [t["net"] if t else None for t in row["tiers"]]}
        if g:
            item["godot_vente"], item["godot_achat"] = g["vente"], g["achat"]
        if f:
            item["fidso_vendre_ht"] = f["vendre_ht"]
            item["fidso_net"] = round(f["vendre_ht"] * (1 - tmp), 2)
            item["fidso_acheter_ttc"] = f.get("acheter_ttc")
        comp.append(item)
    fb = {k: v for k, v in (manual.get("fidso_bijoux_eur_g") or {}).items() if not k.startswith("_") and v is not None}
    calcule = False
    if not fb:  # règle déduite du relevé Fidso Arcachon du 20/11/2026 : spot x titre x coefficient
        sp = out["spot"]
        regle = {"24K": (sp["or_g"], 0.999, 0.76), "22K": (sp["or_g"], 22 / 24, 0.76), "18K": (sp["or_g"], 0.75, 0.76),
                 "14K": (sp["or_g"], 0.585, 0.629), "9K": (sp["or_g"], 0.375, 0.609), "AG 925": (sp["ag_g"], 0.925, 0.61)}
        fb = {k: round(c * t * k2, 2) for k, (c, t, k2) in regle.items()}
        calcule = True
    out["concurrents"] = {
        "argent": comp,
        "bijoux": {"godot": data.get("godot_bijoux"),
                   "fidso": fb or None, "fidso_calcule": calcule,
                   "fidso_date": manual.get("fidso_bijoux_date")},
    }
    out["sources"] = etats

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    ko = [e for e in etats if not e["ok"]]
    print(f"prices.json écrit ({os.path.getsize(a.out)} octets). Sources en échec : "
          f"{[e['id'] for e in ko] or 'aucune'}")


if __name__ == "__main__":
    main()
