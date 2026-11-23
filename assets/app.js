/* LPDO – tarifs internes. Aucune dépendance. Les prix viennent de data/prices.enc.json (chiffré). */
(function () {
  "use strict";

  // ---------- utilitaires (testables sous Node) ----------
  const eur = (v, d = 2) => v == null || isNaN(v) ? "—" :
    new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
  const nb = (v, d = 2) => v == null || isNaN(v) ? "—" :
    new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 0, maximumFractionDigits: d }).format(v);
  const pct = (v, d = 1) => v == null || !isFinite(v) ? "—" : nb(v * 100, d) + " %";
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = s => parseFloat(String(s).replace(",", ".").replace(/\s/g, ""));

  function ecartPct(a, b) { return (a == null || !b) ? null : (a - b) / b * 100; }
  /** Marge brute d'un rachat de bijoux au prix p €/g pour un poids donné (formule du fichier : (CA − achat) × coef). */
  function margeBijou(ligne, prix, poids, coef) {
    const achat = prix * poids, ca = ligne.revente_g * poids, mb = (ca - achat) * coef;
    return { achat, ca, mb, taux: achat ? mb / achat : null };
  }
  const libTranche = (t, i) => t.label ? t.label.replace(/\s+/g, " ").trim() : "Tranche " + (i + 1) + " (montant non précisé)";

  if (typeof module !== "undefined") { module.exports = { ecartPct, margeBijou, eur, pct }; return; }

  // ---------- état ----------
  const S = { data: null, tab: "accueil", filtre: "", sel: {}, edit: {}, catAg: { fr: 1, mod: 1, lin: 1 }, catOr: { pie: 1, lin: 1, mod: 0 }, cmpTier: 2, cmpOr: 6, cmpTierV: 2, cmpOrV: 6, poids: "1", titres: null, libre: { i: 0, prix: "" } };
  const $ = s => document.querySelector(s);
  const vue = $("#vue");

  // ---------- chargement + déchiffrement ----------
  const b64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
  const enB64 = u => btoa(String.fromCharCode(...u));
  const KEY = "lpdo_k";

  async function dechiffrer(enc, raw) {
    const key = await crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["decrypt"]);
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(enc.iv) }, key, b64(enc.ct));
    return JSON.parse(new TextDecoder().decode(pt));
  }
  async function deriver(mdp, enc) {
    const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(mdp), "PBKDF2", false, ["deriveBits"]);
    return new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", salt: b64(enc.salt), iterations: enc.iter, hash: "SHA-256" }, base, 256));
  }
  async function recuperer(url) {
    const r = await fetch(url + "?t=" + Date.now(), { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  async function charger() {
    let enc = null;
    try { enc = await recuperer("data/prices.enc.json"); } catch (e) { enc = null; }
    if (!enc) {  // essai local sans chiffrement
      try { S.data = await recuperer("data/prices.json"); demarrer(); return; }
      catch (e) {
        vue.innerHTML = '<div class="bandeau err">Impossible de charger les tarifs (' + esc(e.message) + '). Ouvre le site depuis son adresse GitHub Pages, pas depuis un fichier local.</div>';
        return;
      }
    }
    const stocke = localStorage.getItem(KEY);
    if (stocke) {
      try { S.raw = b64(stocke); S.data = await dechiffrer(enc, S.raw); demarrer(); return; }
      catch (e) { localStorage.removeItem(KEY); }
    }
    ecranMotDePasse(enc);
  }

  function ecranMotDePasse(enc) {
    vue.innerHTML = '<div class="carte" style="max-width:420px;margin:40px auto;padding:22px"><h2>Accès réservé à l\'agence</h2>' +
      '<p class="aide">Saisis le mot de passe de l\'agence. Il sera mémorisé sur cet appareil.</p>' +
      '<form id="mdp"><input type="password" id="m" autocomplete="current-password" placeholder="Mot de passe" style="width:100%;margin-bottom:10px" autofocus>' +
      '<button class="act" type="submit">Ouvrir</button> <span id="mm" class="neg"></span></form></div>';
    $("#mdp").addEventListener("submit", async e => {
      e.preventDefault();
      $("#mm").textContent = "Vérification…";
      try {
        const raw = await deriver($("#m").value, enc);
        S.data = await dechiffrer(enc, raw); S.raw = raw;
        localStorage.setItem(KEY, enB64(raw));
        demarrer();
      } catch (err) { $("#mm").textContent = "Mot de passe incorrect."; }
    });
  }

  function demarrer() {
    $("#verrou").hidden = false;
    $("#verrou").onclick = () => { localStorage.removeItem(KEY); location.reload(); };
    barreCours(); alertes();
    setInterval(rafraichir, 120000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) rafraichir(); });
    const h = location.hash.slice(1);
    aller(NAMES.includes(h) ? h : "accueil");
  }

  // recharge les tarifs sans F5 (toutes les 2 min et au retour sur l'onglet)
  async function rafraichir() {
    if (!S.data || (document.activeElement && document.activeElement.closest && document.activeElement.closest("#vue") && /INPUT|SELECT/.test(document.activeElement.tagName))) return;
    try {
      let n;
      if (S.raw) n = await dechiffrer(await recuperer("data/prices.enc.json"), S.raw);
      else n = await recuperer("data/prices.json");
      if (n.genere_le === S.data.genere_le) return;
      S.data = n; barreCours(); alertes(); rendre();
    } catch (e) { /* on garde les données déjà affichées */ }
  }

  // variation sur 1 semaine (BullionVault) : vert ▲ si +, rouge ▼ si −
  function varHTML(v, court) {
    if (!v || v.pct == null) return "";
    const c = v.pct > 0 ? "pos" : v.pct < 0 ? "neg" : "neutre", f = v.pct > 0 ? "▲" : v.pct < 0 ? "▼" : "■";
    return ' <span class="var ' + c + '" title="Variation sur une semaine (BullionVault)">' + f + " " + (v.pct > 0 ? "+" : "") + nb(v.pct, 2) + " %" +
      (court ? "" : " <small>(" + (v.eur > 0 ? "+" : "") + eur(v.eur, 0) + "/kg, 1 sem.)</small>") + "</span>";
  }
  function barreCours() {
    const s = S.data.spot;
    $("#spotbar").innerHTML =
      '<span>Or <b>' + eur(s.or_g) + '/g</b> <small>(' + eur(s.or_kg, 0) + '/kg)</small>' + varHTML(s.var_or, true) + '</span>' +
      '<span>Argent <b>' + eur(s.ag_g, 3) + '/g</b> <small>(' + eur(s.ag_kg, 0) + '/kg)</small>' + varHTML(s.var_ag, true) + '</span>' +
      '<span><small>Mis à jour ' + new Date(S.data.genere_le).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) + '</small></span>';
  }

  function alertes() {
    const d = S.data, a = [];
    if (d.demo) a.push(["info", "Mode démonstration : chiffres d'exemple du 20/11/2026, pas les cours du jour."]);
    const age = (Date.now() - new Date(d.genere_le)) / 36e5;
    if (age > 3) a.push(["warn", "Attention : les cours datent de " + nb(age, 0) + " h. Le relevé automatique a peut-être échoué."]);
    if (d.spot.manuel) a.push(["warn", "Un cours est forcé à la main (fichier data/manual.json)."]);
    const ko = (d.sources || []).filter(x => !x.ok);
    if (ko.length) a.push(["warn", "Source indisponible : " + ko.map(x => esc(x.id)).join(", ") + ". Les valeurs concernées sont absentes ou manuelles."]);
    $("#alertes").innerHTML = a.map(x => '<div class="bandeau ' + x[0] + '">' + x[1] + '</div>').join("");
  }

  // ---------- navigation ----------
  const NAMES = ["accueil", "argent_rachat", "argent_vente", "or_rachat", "or_vente", "bijoux", "concurrents"];
  function aller(t) {
    S.tab = t; S.filtre = ""; location.hash = t;
    document.querySelectorAll(".tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === t));
    rendre();
  }
  function rendre() {
    const t = S.tab, y = window.scrollY;
    ({ accueil: vAccueil, bijoux: vBijoux, concurrents: vConcurrents }[t] || (() => vPieces(t)))();
    window.scrollTo(0, y);
  }
  // surbrillance : un clic sur une ligne la repère, un 2e clic l'enlève (mémorisé par tableau)
  vue.addEventListener("click", e => {
    if (e.target.closest("input,select,button,a,th")) return;
    const tr = e.target.closest("tbody tr"); if (!tr || tr.classList.contains("sec")) return;
    const k = tr.closest("[data-sel]"); const cle = (k ? k.dataset.sel : S.tab) + "|" + tr.cells[0].textContent.trim();
    S.sel[cle] ? delete S.sel[cle] : (S.sel[cle] = 1);
    tr.classList.toggle("sel", !!S.sel[cle]);
  });
  const estSel = (zone, nom) => S.sel[zone + "|" + nom] ? " sel" : "";
  document.querySelector(".tabs").addEventListener("click", e => { const b = e.target.closest("button"); if (b && S.data) aller(b.dataset.tab); });

  // ---------- accueil ----------
  function vAccueil() {
    const d = S.data, c = d.cours_utilises;
    vue.innerHTML = '<h2>Cours du moment</h2><div class="grille">' +
      '<div class="kpi"><div class="l">Or (BullionVault)</div><div class="v">' + eur(d.spot.or_kg, 0) + ' /kg</div><div class="l">' + eur(d.spot.or_g) + ' le gramme · ' + esc(d.spot.heure_or || "") + '</div><div class="l">' + (varHTML(d.spot.var_or, false) || "Variation non disponible") + '</div></div>' +
      '<div class="kpi"><div class="l">Argent (BullionVault)</div><div class="v">' + eur(d.spot.ag_kg, 0) + ' /kg</div><div class="l">' + eur(d.spot.ag_g, 3) + ' le gramme · ' + esc(d.spot.heure_ag || "") + '</div><div class="l">' + (varHTML(d.spot.var_ag, false) || "Variation non disponible") + '</div></div>' +
      '<div class="kpi"><div class="l">Taxe métaux précieux (TMP)</div><div class="v">' + nb(d.tmp * 100, 1) + ' %</div><div class="l">déduite dans les tableaux de rachat</div></div></div>' +
      '<h3>Cours utilisés dans les tableaux</h3><p class="aide">Argent : ' + eur(c.argent, 0) + '/kg · Or rachat : ' + eur(c.or_rachat, 0) + '/kg · Or vente : ' + eur(c.or_vente, 0) + '/kg</p>' +
      '<h3>État des sources</h3><div>' + (d.sources || []).map(x => '<span class="pastille ' + (x.ok ? "ok" : "ko") + '" title="' + esc(x.message) + '">' + (x.ok ? "✓ " : "✗ ") + esc(x.id) + (x.message ? " · " + esc(x.message) : "") + '</span>').join("") + '</div>' +
      '<h3>Comment ça marche</h3><p class="aide">Les cours sont lus automatiquement toutes les 30 minutes (jours ouvrés et samedi). Les tableaux reprennent les mêmes colonnes et les mêmes formules que les fichiers Excel. Rien à saisir.</p>';
  }

  // ---------- pièces : tableaux détaillés comme dans les fichiers ----------
  const mnt = (v, signe, d = 2) => v == null ? '<td class="vide">—</td>' : "<td>" + (signe < 0 && v ? "− " + eur(v, d) : eur(v, d)) + "</td>";

  function vPieces(t) {
    const d = S.data[t], achat = t.endsWith("rachat"), argent = t.startsWith("argent");
    const cours = S.data.cours_utilises[argent ? "argent" : t];
    const par = achat ? 4 : 2, nT = d.tiers.length;
    const titre = (achat ? "Rachat " : "Vente ") + (argent ? "pièces et lingots d'argent" : "pièces et lingots d'or");
    const entete =
      '<tr><th rowspan="3">Désignation</th><th rowspan="3">Poids (g)</th><th rowspan="3">Titre</th><th rowspan="3">Cours<small>valeur brute</small></th>' +
      (achat ? '<th rowspan="3">Frais<small>' + (argent ? "non boursable" : "fonte") + '</small></th>' : "") +
      d.tiers.map((x, i) => '<th colspan="' + par + '" class="g' + (i % 2) + '">COMMISSION ' + nb(x.commission * 100, 1) + ' %</th>').join("") + '</tr>' +
      '<tr>' + d.tiers.map((x, i) => '<th colspan="' + par + '" class="g' + (i % 2) + ' plage">' + esc(libTranche(x, i)) + '</th>').join("") + '</tr>' +
      '<tr>' + d.tiers.map((x, i) => (achat
        ? ['Commission', 'Valeur', 'TMP ' + nb(S.data.tmp * 100, 1) + ' %', 'Net client']
        : ['Commission', 'Vente']).map((h, k) => '<th class="g' + (i % 2) + (k === par - 1 ? " fin" : "") + '">' + h + '</th>').join("")).join("") + '</tr>';
    let last = null, corps = "";
    const ncol = 4 + (achat ? 1 : 0) + nT * par;
    const editable = r => achat && /^(AUTRES PIECES|HORS COTE)$/i.test(r.name);
    const cellsCalc = (r, poids, titre) => {   // recalcul côté navigateur pour les lignes saisissables
      if (poids === r.poids && titre === r.titre) return { brut: r.brut, frais: r.frais, tiers: r.tiers };
      const brut = poids * titre * cours / 1000, frais = brut * r.frais_pct, tmpR = S.data.tmp;
      return { brut, frais, tiers: d.tiers.map(x => {
        const comm = brut * x.commission;
        if (argent) { const valeur = brut - frais - comm, tmp = valeur * tmpR; return { commission: comm, valeur, tmp, net: valeur - tmp }; }
        const tmp = (brut - comm) * tmpR;
        return { commission: comm, valeur: brut - frais - comm, tmp, net: Math.floor(Math.round((brut - tmp - frais - comm) * 1e9) / 1e9) };
      }) };
    };
    const calcTds = (r, c) => mnt(c.brut, 1).replace("<td", '<td class="calc"') +
        (achat ? (c.frais ? mnt(c.frais, -1).replace("<td", '<td class="calc"') : '<td class="vide calc">—</td>') : "") +
        c.tiers.map((x, i) => {
          const g = "g" + (i % 2) + " calc";
          if (!x) return '<td class="vide ' + g + '" colspan="' + par + '">—</td>';
          return (achat
            ? mnt(x.commission, -1).replace("<td", '<td class="' + g + '"') + mnt(x.valeur, 1).replace("<td", '<td class="calc"') + mnt(x.tmp, -1).replace("<td", '<td class="calc"') + mnt(x.net, 1).replace("<td>", '<td class="net calc">')
            : mnt(x.commission, 1).replace("<td", '<td class="' + g + '"') + mnt(x.prix, 1).replace("<td>", '<td class="net calc">'));
        }).join("");
    const lecture = (r) => { const e = S.edit[t + "|" + r.name]; return e ? e : { poids: r.poids, titre: r.titre }; };
    d.rows.forEach(r => {
      if (r.section && r.section !== last) { corps += '<tr class="sec"><td colspan="' + ncol + '">' + esc(r.section) + '</td></tr>'; last = r.section; }
      const v = editable(r) ? lecture(r) : { poids: r.poids, titre: r.titre };
      const c = editable(r) ? cellsCalc(r, v.poids, v.titre) : { brut: r.brut, frais: r.frais, tiers: r.tiers };
      const pT = editable(r)
        ? '<td class="in"><input class="ed" data-k="poids" value="' + nb(v.poids, 3) + '" inputmode="decimal" aria-label="Poids"> g</td><td class="in"><input class="ed" data-k="titre" value="' + nb(v.titre * 100, 2) + '" inputmode="decimal" aria-label="Titre"> %</td>'
        : '<td>' + nb(r.poids, 3) + '</td><td>' + nb(r.titre * 100, 1) + ' %</td>';
      corps += '<tr data-n="' + esc(r.name) + '" class="' + (editable(r) ? "edl" : "") + estSel(t, r.name) + '"><td>' + esc(r.name) + '</td>' + pT + calcTds(r, c) + '</tr>';
    });
    vue.innerHTML = '<h2>' + titre + '</h2>' +
      '<p class="aide"><b>COURS LINGOT : ' + eur(cours, 0) + ' /kg</b>' + (achat ? ' · TMP ' + nb(S.data.tmp * 100, 1) + ' %. Le net client = cours − frais − commission − TMP.' : '. Prix de vente = cours + commission.') +
      ' Les lingots et lingotins ajoutent leur prime au cours.</p>' +
      '<div class="outils"><input type="search" id="f" placeholder="Filtrer (ex. napoléon, maple…)" value="' + esc(S.filtre) + '"></div>' +
      '<div class="carte large"><table class="det"><thead>' + entete + '</thead><tbody>' + corps + '</tbody></table></div>' +
      (achat && d.rows.some(editable) ? '<p class="aide">Sur les lignes <b>AUTRES PIECES</b>' + (argent ? "" : " et <b>HORS COTE</b>") + ', tape le poids (en g) et le titre (en %, ex. 90 ou 900) : les montants se recalculent.</p>' : "");
    vue.querySelector("#f").addEventListener("input", e => { S.filtre = e.target.value; filtrer(); });
    vue.querySelectorAll("tr.edl").forEach(tr => tr.addEventListener("input", e => {
      const r = d.rows.find(x => x.name === tr.dataset.n), cur = lecture(r), k = e.target.dataset.k;
      let n = num(e.target.value); if (!(n > 0)) return;
      if (k === "titre") n = n > 100 ? n / 1000 : n / 100;
      const v = { poids: k === "poids" ? n : cur.poids, titre: k === "titre" ? Math.min(n, 1) : cur.titre };
      S.edit[t + "|" + r.name] = v;
      tr.querySelectorAll(".calc").forEach(td => td.remove());
      tr.insertAdjacentHTML("beforeend", calcTds(r, cellsCalc(r, v.poids, v.titre)));
    }));
    filtrer();
  }
  function filtrer() {
    const f = S.filtre.trim().toLowerCase();
    vue.querySelectorAll("tbody tr").forEach(tr => {
      tr.hidden = tr.classList.contains("sec") ? !!f : (f && !tr.firstChild.textContent.toLowerCase().includes(f));
    });
  }

  // ---------- bijoux : tableau de base, grille de prix et marges ----------
  const nomBij = b => b.label.startsWith("AG") ? b.label + (b.label === "AG 835" ? " (Semeuse)" : b.label === "AG 680" ? " (Turin)" : "")
    : "Or " + b.label + (b.blanc_rose ? " blanc/rose" : "");
  const decPrix = (b, p) => Number.isInteger(+p) ? 0 : (b.metal === "argent" ? 3 : 2);
  const cls = v => v == null ? "" : v < 0 ? "neg" : "pos";
  const SEUIL = 0.15;  // marge < 15 % : rouge
  const clsT = t => t == null ? "" : t < SEUIL ? "neg" : "pos";
  const bx = () => (S.data.concurrents.godot_bordeaux_delta != null ? S.data.concurrents.godot_bordeaux_delta : -5);

  function vBijoux() {
    const B = S.data.bijoux, L = B.lignes;
    if (!S.titres) S.titres = new Set(L.map((b, i) => i));
    const ligne = (lib, f) => '<tr><td>' + lib + '</td>' + L.map(b => '<td>' + f(b) + '</td>').join("") + '</tr>';
    vue.innerHTML = '<h2>Rachat de bijoux</h2><p class="aide">Mêmes lignes que « Rachat Bijoux BASE » : prix net, revente à la fonte, marge. La grille ci-dessous donne la marge pour chaque prix que tu peux proposer.</p>' +
      '<div class="carte large" data-sel="base"><table class="bij"><thead><tr><th>Par gramme</th>' + L.map(b => '<th>' + esc(nomBij(b)) + '</th>').join("") + '</tr></thead><tbody>' +
      ligne("Prix rachat net", b => '<b>' + eur(b.net_gramme, decPrix(b, b.net_gramme)) + '</b>') +
      ligne("Revente fonte", b => eur(b.revente_g, 2)) +
      ligne("Marge / gramme", b => '<span class="' + clsT(b.taux_marge) + '">' + eur(b.marge_g, 2) + '</span>') +
      ligne("Taux de marge", b => '<span class="' + clsT(b.taux_marge) + '">' + pct(b.taux_marge, 1) + '</span>') +
      ligne("Valo gramme brut", b => eur(b.valeur_gramme, 2)) +
      '</tbody></table></div>' +
      '<h3>Grille des prix possibles</h3>' +
      '<div class="outils">Poids en gr : <input type="text" id="poids" inputmode="decimal" value="' + esc(S.poids) + '" style="width:80px"> ' +
      '<span class="aide">Titres affichés :</span> <button class="pill tt" data-all="1">Tous</button><button class="pill tt" data-all="0">Aucun</button> ' + L.map((b, i) => '<button class="pill' + (S.titres.has(i) ? " on" : "") + '" data-t="' + i + '">' + esc(nomBij(b)) + '</button>').join("") + '</div>' +
      '<div id="grille" class="carte large" data-sel="grille"></div>' +
      '<h3>Prix libre</h3><div class="outils">' +
      '<select id="lt">' + L.map((b, i) => '<option value="' + i + '"' + (S.libre.i === i ? " selected" : "") + '>' + esc(nomBij(b)) + '</option>').join("") + '</select>' +
      'prix proposé /g <input type="text" id="lp" inputmode="decimal" value="' + esc(S.libre.prix) + '" placeholder="' + eur(L[S.libre.i].net_gramme, decPrix(L[S.libre.i], L[S.libre.i].net_gramme)) + '" style="width:90px"></div>' +
      '<div id="libre" class="carte" style="padding:12px 16px"></div>';
    vue.querySelector("#poids").addEventListener("input", e => { S.poids = e.target.value; grilleBij(); libreBij(); });
    vue.querySelector(".outils").addEventListener("click", e => {
      const b = e.target.closest(".pill"); if (!b) return;
      if (b.dataset.all) { S.titres = b.dataset.all === "1" ? new Set(L.map((x, i) => i)) : new Set(); vBijoux(); return; }
      const i = +b.dataset.t; S.titres.has(i) ? S.titres.delete(i) : S.titres.add(i); b.classList.toggle("on"); grilleBij();
    });
    vue.querySelector("#lt").addEventListener("change", e => { S.libre.i = +e.target.value; vBijoux(); });
    vue.querySelector("#lp").addEventListener("input", e => { S.libre.prix = e.target.value; libreBij(); });
    grilleBij(); libreBij();
  }

  function concBij(b) {
    const C = S.data.concurrents.bijoux, out = [];
    const g = C.godot, f = C.fidso;
    if (b.metal === "or" && !b.blanc_rose) {
      if (g && g[b.label] != null) { out.push(["Godot.fr", g[b.label]]); out.push(["Godot Bordeaux", g[b.label] + bx()]); }
      if (f && f[b.label] != null) out.push(["Fidso", f[b.label]]);
    } else if (b.label === "AG 925" && f && f["AG 925"] != null) out.push(["Fidso", f["AG 925"]]);
    return out;
  }

  function grilleBij() {
    const B = S.data.bijoux, mc = B.marge_coef, P = num(S.poids) || 1;
    const sel = [...S.titres].sort((a, b) => a - b).map(i => B.lignes[i]);
    const el = vue.querySelector("#grille");
    if (!sel.length) { el.innerHTML = '<p class="aide" style="padding:12px">Choisis au moins un titre.</p>'; return; }
    const cell = (b, p, extra) => {
      const m = margeBijou(b, p, P, mc);
      return '<td class="' + extra + '">' + eur(p, decPrix(b, p)) + '</td><td>' + eur(m.achat, 2) + '</td><td class="' + clsT(m.taux) + '">' + eur(m.mb, 2) + '</td><td class="fin ' + clsT(m.taux) + '">' + pct(m.taux, 1) + '</td>';
    };
    let html = '<table class="det bij"><thead><tr><th rowspan="2">Prix</th>' + sel.map((b, i) => '<th colspan="4" class="g' + (i % 2) + '">' + esc(nomBij(b)) + '<small>revente fonte ' + eur(b.revente_g, 2) + '/g</small></th>').join("") + '</tr><tr>' +
      sel.map((b, i) => ["Prix /g", "Achat client", "MB", "% marge"].map((h, k) => '<th class="g' + (i % 2) + (k === 3 ? " fin" : "") + '">' + h + '</th>').join("")).join("") + '</tr></thead><tbody>';
    // lignes concurrents
    ["Godot.fr", "Godot Bordeaux", "Fidso"].forEach(nom => {
      if (!sel.some(b => concBij(b).some(c => c[0] === nom))) return;
      html += '<tr class="conc' + estSel("grille", nom + (nom === "Godot Bordeaux" ? " (" + eur(bx(), 0) + " vs godot.fr)" : " (concurrent)")) + '"><td>' + nom + (nom === "Godot Bordeaux" ? " (" + eur(bx(), 0) + " vs godot.fr)" : " (concurrent)") + '</td>' + sel.map(b => {
        const c = concBij(b).find(x => x[0] === nom);
        return c ? cell(b, c[1], "") : '<td class="vide" colspan="4">—</td>';
      }).join("") + '</tr>';
    });
    const max = Math.max(...sel.map(b => b.prix.length));
    for (let k = 0; k < max; k++) {
      html += '<tr class="' + (k === 0 ? "base" : "") + estSel("grille", k === 0 ? "Tarif actuel" : "+ palier " + k) + '"><td>' + (k === 0 ? "Tarif actuel" : "+ palier " + k) + '</td>' +
        sel.map(b => k < b.prix.length ? cell(b, b.prix[k], k === 0 ? "net" : "") : '<td class="vide" colspan="4"></td>').join("") + '</tr>';
    }
    el.innerHTML = html + '</tbody></table>';
  }

  function libreBij() {
    const B = S.data.bijoux, b = B.lignes[S.libre.i], P = num(S.poids) || 1;
    const p = num(S.libre.prix) || b.net_gramme, m = margeBijou(b, p, P, B.marge_coef);
    vue.querySelector("#libre").innerHTML = 'Pour <b>' + nb(P, 2) + ' g</b> de ' + esc(nomBij(b)) + ' à <b>' + eur(p, decPrix(b, p)) + '/g</b> : ' +
      'achat client <b>' + eur(m.achat) + '</b> · revente fonte <b>' + eur(m.ca) + '</b> · marge brute <b class="' + clsT(m.taux) + '">' + eur(m.mb) + '</b> (<b class="' + clsT(m.taux) + '">' + pct(m.taux, 1) + '</b>)';
  }

  // ---------- concurrents ----------
  const badge = p => p == null ? '<span class="neutre">—</span>' : '<span class="' + (p >= 0 ? "pos" : "neg") + '">' + (p >= 0 ? "+" : "") + nb(p, 1) + " %</span>";
  const badgeV = p => p == null ? '<span class="neutre">—</span>' : '<span class="' + (p <= 0 ? "pos" : "neg") + '">' + (p >= 0 ? "+" : "") + nb(p, 1) + " %</span>";
  function selTranche(id, tiers, cur) {
    return '<div class="outils">Tranche LPDO comparée : <select id="' + id + '">' +
      tiers.map((x, i) => '<option value="' + i + '"' + (i === cur ? " selected" : "") + '>Commission ' + nb(x.commission * 100, 1) + ' %</option>').join("") + '</select></div>';
  }
  const catAg = n => /lingot|\bkg\b/i.test(n) ? "lin" : /\bfr\b|franc|ecu|semeuse|hercule|turin/i.test(n) ? "fr" : "mod";
  const catOr = n => /^lingot/i.test(n) ? "lin" : /^(maple leaf|american eagle|philarmonique|britannia|panda|american buffalo|nugget)/i.test(n) ? "mod" : "pie";
  function barreCat() {
    const g = (etiq, cats, etat, id) => '<span class="aide">' + etiq + ' :</span> ' + cats.map(([k, l]) =>
      '<button class="pill' + (etat[k] ? " on" : "") + '" data-g="' + id + '" data-k="' + k + '">' + l + '</button>').join("") + ' ';
    return '<div class="outils">' + g("Argent", [["fr", "Pièces françaises"], ["mod", "Pièces modernes"], ["lin", "Lingots et lingotins"]], S.catAg, "ag") +
      '&nbsp;&nbsp;' + g("Or", [["pie", "Pièces"], ["lin", "Lingots et lingotins"], ["mod", "Pièces modernes 1 once"]], S.catOr, "or") + '</div>';
  }
  function vConcurrents() {
    const D = S.data, C = D.concurrents, B = D.bijoux, tmp = D.tmp;
    const fid = C.bijoux.fidso, god = C.bijoux.godot;
    const net = v => v == null ? null : v * (1 - tmp);
    const vide = (n, m) => '<tr><td colspan="' + n + '" class="neutre">' + m + '</td></tr>';
    const rachat = (liste, idx, avecFid) => (liste || []).map(c => { const l = c.lpdo[idx], gn = net(c.godot_vente);
      return '<tr><td>' + esc(c.name) + '</td><td><b>' + eur(l) + '</b></td><td>' + eur(c.godot_vente) + '</td><td>' + eur(gn) + '</td><td>' + badge(ecartPct(l, gn)) + '</td>' +
        (avecFid ? '<td>' + eur(c.fidso_net) + '</td><td>' + badge(ecartPct(l, c.fidso_net)) + '</td>' : "") + '</tr>'; }).join("");
    const vente = (liste, idx) => (liste || []).map(c => { const l = c.lpdo[idx];
      return '<tr><td>' + esc(c.name) + '</td><td><b>' + eur(l) + '</b></td><td>' + eur(c.godot_achat) + '</td><td>' + badgeV(ecartPct(l, c.godot_achat)) + '</td></tr>'; }).join("");
    const fAg = l => (l || []).filter(c => S.catAg[catAg(c.name)]), fOr = l => (l || []).filter(c => S.catOr[catOr(c.name)]);
    const rowsAg = rachat(fAg(C.argent), S.cmpTier, true), rowsOr = rachat(fOr(C.or), S.cmpOr);
    const rowsAgV = vente(fAg(C.argent_vente), S.cmpTierV), rowsOrV = vente(fOr(C.or_vente), S.cmpOrV);
    const bij = ["24K", "22K", "18K", "14K", "9K"].map(k => {
      const b = B.lignes.find(x => x.label === k && !x.blanc_rose);
      const g = god && god[k], f = fid && fid[k];
      const al = (v) => { if (!b || v == null) return '<td class="neutre">—</td>'; const m = margeBijou(b, v, 1, B.marge_coef); return '<td><span class="' + clsT(m.taux) + '">' + eur(m.mb, 2) + ' (' + pct(m.taux, 1) + ')</span></td>'; };
      return '<tr><td>Or ' + k + '</td><td><b>' + eur(b && b.net_gramme) + '</b></td><td>' + eur(g) + '</td><td>' + badge(ecartPct(b && b.net_gramme, g)) + '</td>' + al(g) +
        '<td>' + eur(g == null ? null : g + bx()) + '</td><td>' + badge(ecartPct(b && b.net_gramme, g == null ? null : g + bx())) + '</td>' + al(g == null ? null : g + bx()) +
        '<td>' + eur(f) + '</td><td>' + badge(ecartPct(b && b.net_gramme, f)) + '</td>' + al(f) + '</tr>';
    }).join("");
    const hd = (a, extra) => '<div class="carte" data-sel="conc' + a + '"><table><thead><tr><th>Pièce</th><th>LPDO ' + a + '</th>' + extra + '</tr></thead><tbody>';
    vue.innerHTML = '<h2>Comparatif concurrents</h2><p class="aide">Rachat : écart = LPDO par rapport au concurrent (<span class="pos">vert</span> : on paie plus cher le client, <span class="neg">rouge</span> : moins cher). Vente : <span class="pos">vert</span> si on vend moins cher que Godot, <span class="neg">rouge</span> si plus cher. Marges en <span class="neg">rouge</span> sous 15 %.</p>' + barreCat() +
      '<h3>Rachat pièces et lingots argent</h3>' + selTranche("ct", D.argent_rachat.tiers, S.cmpTier) +
      hd("net", '<th>Godot.fr « Vente » (HT)</th><th>Godot net (− TMP ' + nb(tmp * 100, 1) + ' %)</th><th>Écart</th><th>Fidso net (HT − TMP)</th><th>Écart</th>') +
      (rowsAg || vide(7, "Aucune donnée concurrent disponible.")) + '</tbody></table></div>' +
      '<p class="aide">Godot.fr affiche ses prix hors TMP : on retire ' + nb(tmp * 100, 1) + ' % pour comparer au net client LPDO. Fidso Arcachon : « Vendre HT » × (1 − ' + nb(tmp * 100, 1) + ' % de TMP).</p>' +
      '<h3>Rachat pièces et lingots or</h3>' + selTranche("co", D.or_rachat.tiers, S.cmpOr) +
      hd("net", '<th>Godot.fr « Vous vendez » (HT)</th><th>Godot net (− TMP ' + nb(tmp * 100, 1) + ' %)</th><th>Écart</th>') +
      (rowsOr || vide(5, "Aucune donnée Godot pour l\'or (voir l\'état des sources sur l\'accueil).")) + '</tbody></table></div>' +
      '<h3>Vente pièces et lingots argent</h3>' + selTranche("cta", D.argent_vente.tiers, S.cmpTierV) +
      hd("vente", '<th>Godot.fr « Vous achetez »</th><th>Écart</th>') + (rowsAgV || vide(4, "Aucune donnée Godot.")) + '</tbody></table></div>' +
      '<h3>Vente pièces et lingots or</h3>' + selTranche("coa", D.or_vente.tiers, S.cmpOrV) +
      hd("vente", '<th>Godot.fr « Vous achetez »</th><th>Écart</th>') + (rowsOrV || vide(4, "Aucune donnée Godot.")) + '</tbody></table></div>' +
      '<p class="aide">Vente : prix auquel le client achète chez Godot.fr (« Vous achetez ») comparé à notre prix de vente de la tranche choisie.</p>' +
      '<h3>Rachat bijoux or (au gramme)</h3><div class="carte large"><table><thead><tr><th>Titre</th><th>LPDO net/g</th><th>Godot.fr /g</th><th>Écart</th><th>Notre marge si on s\'aligne</th><th>Godot Bordeaux /g</th><th>Écart</th><th>Notre marge si on s\'aligne</th><th>Fidso /g</th><th>Écart</th><th>Notre marge si on s\'aligne</th></tr></thead><tbody>' + bij + '</tbody></table></div>' +
      '<p class="aide">Godot.fr : prix de l\'estimateur du site godot.fr (kit postal, minimum 100 €). Fidso : ' +
      (fid && C.bijoux.fidso_calcule ? "calculé d'après le relevé du 20/11/2026 (spot × titre × coefficient : 76 % pour 24K/22K/18K, 62,9 % pour 14K, 60,9 % pour 9K, 61 % pour l'argent), à confirmer avec un 2e relevé" : fid ? "saisi à la main" + (C.bijoux.fidso_date ? " le " + esc(C.bijoux.fidso_date) : "") + " dans data/manual.json." : "pas encore saisi (voir data/manual.json).") +
      ' La marge « si on s\'aligne » utilise la formule du fichier bijoux : (revente fonte − prix) × ' + nb(B.marge_coef, 4) + '. Pour tous les prix intermédiaires, voir la grille de l\'onglet Rachat bijoux.</p>';
    vue.querySelectorAll(".pill[data-g]").forEach(b => b.addEventListener("click", () => {
      const o = b.dataset.g === "ag" ? S.catAg : S.catOr; o[b.dataset.k] = o[b.dataset.k] ? 0 : 1; vConcurrents();
    }));
    [["ct", "cmpTier"], ["co", "cmpOr"], ["cta", "cmpTierV"], ["coa", "cmpOrV"]].forEach(([id, k]) =>
      vue.querySelector("#" + id).addEventListener("change", e => { S[k] = +e.target.value; vConcurrents(); }));
  }

  charger();
})();
