"""Lecture des sources en ligne (cours, cotations, concurrents).

Chaque lecteur est séparé en deux parties : récupération de la page (navigateur
Playwright, car certains prix sont chargés par JavaScript) et analyse du texte
(fonctions parse_*, testées sur des exemples dans tools/test_parsers.py).
"""
import re
import unicodedata
from html.parser import HTMLParser

try:  # Playwright n'est installé que dans GitHub Actions
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None

URL_OR = "https://or.bullionvault.fr/Cours-De-L-Or.do"
URL_ARGENT = "https://or.bullionvault.fr/Cours-De-L-Argent-Metal.do"
URL_GOLDFR = "https://www.gold.fr/cours-argent-prix-de-l-argent/"
URL_GODOT_ARGENT = "https://www.achat-or-et-argent.fr/argent/cours-de-l-argent"
URL_GODOT_OR = "https://www.achat-or-et-argent.fr/or/cours-de-l-or"
URL_GODOT_BIJOUX = "https://www.achat-or-et-argent.fr/rachat-de-bijoux/commander-son-kit"
URL_FIDSO = "https://www.fidso-or.com/arcachon/{cat}/{slug}"

OZ_G = 31.1034768


# ---------------------------------------------------------------- utilitaires
def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def parse_eur(s):
    """'1 240,00 €' / '1 250.77 €' / '99.73' -> float (None si illisible)."""
    if s is None:
        return None
    s = re.sub(r"[\s  €]", "", str(s))
    m = re.search(r"-?\d[\d.,]*", s)
    if not m:
        return None
    s = m.group(0)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._in_cell = [], None, [], False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._in_cell, self._cell = True, []
        elif tag == "a" and self._in_cell:
            self._cell.append("")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._in_cell = False
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in_cell:
            self._cell.append(data)


def html_rows(html):
    p = _Tables()
    p.feed(html or "")
    return p.rows


# ------------------------------------------------------------------ analyse
def parse_bullionvault(text):
    """Renvoie (euros par kilo, horodatage texte) depuis le texte de la page."""
    t = re.sub(r"[  ]", " ", text or "")
    m = re.search(r"par\s+kilo(?:gramme)?\D{0,40}?(\d[\d ]*(?:[.,]\d+)?)\s*€", t, re.I)
    kg = parse_eur(m.group(1)) if m else None
    if kg is None:
        m = re.search(r"par\s+once\D{0,40}?(\d[\d ]*(?:[.,]\d+)?)\s*€", t, re.I)
        if m:
            kg = parse_eur(m.group(1)) * 1000 / OZ_G
    when = re.search(r"(\d{1,2}\s+\w+\s+20\d\d,?\s+\d{1,2}:\d{2}:\d{2}[^|\n]*)", t)
    return kg, (when.group(1).strip() if when else None)


def parse_variation_semaine(text):
    """Variation sur une semaine affichée par BullionVault : « Une Semaine Variation | -9 375,45 € (8,29 %) ».
    Renvoie {'eur': -9375.45, 'pct': -8.29} (le signe du pourcentage est celui du montant) ou None."""
    t = re.sub(r"[\u00a0\u202f]", " ", text or "")
    m = re.search(r"Une\s+Semaine\s+Variation\D{0,15}?([-−+]?)\s*(\d[\d ]*(?:[.,]\d+)?)\s*€\s*\(\s*([-−+]?)\s*(\d+(?:[.,]\d+)?)\s*%", t, re.I)
    if not m:
        return None
    eur = parse_eur(m.group(2)); pct = parse_eur(m.group(4))
    if eur is None or pct is None:
        return None
    neg = (m.group(1) or m.group(3)) in ("-", "−")
    sg = -1 if neg else 1
    return {"eur": sg * eur, "pct": sg * pct}


def parse_goldfr(html):
    """{nom normalisé: {'nom', 'prix', 'prime'}} depuis le tableau de gold.fr.
    Tolère une colonne vide (miniature) avant l'intitulé : le nom est la première cellule
    avec des lettres, suivie d'une cellule contenant un prix."""
    out = {}
    for cells in html_rows(html):
        for i in range(len(cells) - 1):
            nom = cells[i].strip()
            if not re.search(r"[A-Za-zÀ-ÿ]{3}", nom) or "€" in nom:
                continue
            prix = parse_eur(cells[i + 1])
            if prix is None:
                continue
            pcts = [c for c in cells[i + 2:] if "%" in c]  # variation puis prime : on prend la dernière
            prime = parse_eur(pcts[-1]) if pcts else None
            out[norm(nom)] = {"nom": nom, "prix": prix, "prime": prime}
            break
    return out


def parse_godot_argent(html):
    """{nom normalisé: {'nom','valeur','achat','vente'}} pour les tableaux de achat-or-et-argent.fr
    (argent comme or). Tolère colonnes vides ou en plus : le nom est la première cellule avec des
    lettres sans prix ; 'achat' et 'vente' sont les deux derniers montants en euros de la ligne
    (« Vous achetez » / « Vous vendez » : vente = ce que le client reçoit)."""
    out = {}
    for cells in html_rows(html):
        nom = next((c.strip() for c in cells if re.search(r"[A-Za-zÀ-ÿ]{3}", c) and "€" not in c and "%" not in c), None)
        montants = [parse_eur(c) for c in cells if "€" in c]
        montants = [m for m in montants if m is not None]
        if not nom or len(montants) < 2:
            continue
        out[norm(nom)] = {"nom": nom, "valeur": montants[0] if len(montants) >= 3 else None,
                          "achat": montants[-2], "vente": montants[-1]}
    return out


parse_godot_or = parse_godot_argent


def parse_godot_bijoux(text):
    """{'24K': 99.73, ..., 'argent_pieces_g': 1.0085} depuis le texte rendu."""
    t = re.sub(r"[  ]", " ", text or "")
    out = {}
    for carat in (24, 22, 18, 14, 9):
        m = re.search(rf"\b{carat}\s*carats?\s+(?:\d+(?:[.,]\d+)?\s+)?(\d+[.,]\d+)\s*€", t, re.I)
        if m:
            out[f"{carat}K"] = parse_eur(m.group(1))
    m = re.search(r"Pi[èe]ces?\s+Argent\s+(?:\d+(?:[.,]\d+)?\s+)?(\d+[.,]\d+)\s*€", t, re.I)
    if m:
        out["argent_pieces_g"] = parse_eur(m.group(1))
    return out


def parse_fidso_produit(text):
    t = re.sub(r"[  ]", " ", text or "")
    res = {}
    for key, pat in (("vendre_ht", r"Vendre\s*HT\D{0,40}?(\d[\d ]*[.,]\d{2})"),
                     ("acheter_ttc", r"Acheter\s*TTC\D{0,40}?(\d[\d ]*[.,]\d{2})"),
                     ("cours_fr", r"Cours\s*FR\D{0,40}?(\d[\d ]*[.,]\d{2})")):
        m = re.search(pat, t, re.I)
        if m:
            res[key] = parse_eur(m.group(1))
    return res


# --------------------------------------------------------------- navigateur
class Navigateur:
    """Petit enrobage de Playwright : renvoie (html, texte) d'une page rendue."""

    def __enter__(self):
        if sync_playwright is None:
            raise RuntimeError("Playwright n'est pas installé")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._ctx = self._browser.new_context(
            locale="fr-FR", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        return self

    def __exit__(self, *a):
        self._browser.close()
        self._pw.stop()

    def page(self, url, attendre_texte=None, timeout=30000):
        p = self._ctx.new_page()
        try:
            p.goto(url, wait_until="domcontentloaded", timeout=timeout)
            try:
                p.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            if attendre_texte:
                p.wait_for_function(
                    "t => new RegExp(t, 'i').test(document.body.innerText)",
                    arg=attendre_texte, timeout=timeout)
            return p.content(), p.inner_text("body")
        finally:
            p.close()
