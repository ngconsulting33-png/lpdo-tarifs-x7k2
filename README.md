# LPDO – Tarifs internes

Mini site pour l'agence : rachat et vente de pièces (argent et or), rachat de bijoux, et comparatif
avec Godot (achat-or-et-argent.fr) et Fidso Arcachon. Les cours sont lus tout seuls sur BullionVault ;
les cotations des pièces d'argent « boursable » sur gold.fr. **Plus aucune saisie dans Google Sheets.**

## Mise en ligne (une seule fois, environ 10 minutes)

1. **Créer un dépôt GitHub** avec un nom peu devinable, par exemple `lpdo-tarifs-x7k2`, et y envoyer tout le contenu de ce dossier
   (*Add file → Upload files*). Le dossier `.github/workflows/` est caché sur Mac : s'il n'est pas parti,
   crée le fichier à la main (*Add file → Create new file*, nom `.github/workflows/mise-a-jour.yml`) et colle le contenu
   de `github-workflow-mise-a-jour.yml`.
2. **Ajouter les règles privées** : *Settings → Secrets and variables → Actions → New repository secret*,
   nom `RULES_JSON`, valeur = tout le contenu du fichier `RULES_JSON.txt` (livré à part, **ne jamais l'envoyer sur GitHub**).
3. **Choisir le mot de passe de l'agence** : même endroit, nouveau secret `SITE_PASSPHRASE`, valeur = un mot de passe
   d'au moins 12 caractères (une phrase fait très bien l'affaire). Les tarifs sont publiés **chiffrés** : sans ce mot de passe,
   le site n'affiche rien. À donner à l'équipe ; chaque appareil le mémorise (bouton *Verrouiller* pour l'oublier).
   Pour le changer : modifier le secret puis relancer le workflow.
4. **Activer Pages** : *Settings → Pages → Source : GitHub Actions*.
5. **Lancer une première fois** : onglet *Actions → Mise à jour des tarifs → Run workflow*.
   Au bout de 2–3 minutes, l'adresse du site apparaît dans *Settings → Pages* : `https://<compte>.github.io/<nom-du-dépôt>/`.

Ensuite le site se met à jour tout seul toutes les 30 minutes (du lundi au samedi, vers 7 h–20 h).

## Au quotidien

- Ouvre le lien. Rubriques : *Cours & état*, *Rachat/Vente pièces argent*, *Rachat/Vente pièces or*, *Rachat bijoux*, *Concurrents*.
- Dans les rubriques pièces, saisis les quantités : la tranche de commission se choisit selon la valeur du lot, et tu peux la forcer.
- La page *Cours & état* montre si chaque source a bien été lue (vert) ou non (rouge).
- Si une source plante, le site garde le dernier état publié et affiche un bandeau d'alerte.

## Fichier `data/manual.json` (à modifier directement sur GitHub : crayon, puis *Commit*)

- `spot_override` : forcer le cours de l'or / de l'argent (en € par **kilo**) si BullionVault est indisponible.
- `cotations_override` : forcer une cotation d'argent boursable si gold.fr est indisponible.
- `fidso_bijoux_eur_g` : prix de rachat bijoux de Fidso Arcachon (à recopier depuis leur page « Vendre »), avec `fidso_bijoux_date`.

## Modifier les coefficients, commissions ou tranches

Les règles viennent de tes classeurs Excel. Après un changement :

```
python3 tools/build_rules_from_xlsx.py Achat_Vente_pièces.xlsx Tarif_achat_Bijoux.xlsx config/rules.private.json
python3 tools/test_against_xlsx.py Achat_Vente_pièces.xlsx Tarif_achat_Bijoux.xlsx config/rules.private.json
```

puis recopie le contenu du fichier (en une seule ligne, sans espaces superflus) dans le secret `RULES_JSON`.
Le second script compare 927 valeurs du moteur avec celles d'Excel (les écarts connus sont listés ci-dessous).

## Écarts volontaires avec les fichiers Excel

- **Kookabura 1 kg (rachat argent)** : la formule Excel pointait sur la case du 100 F argent ; ici elle utilise la bonne cotation.
- **Rachat pièces d'or, tranche 2 %** : Excel reprend la taxe de la tranche 3 % ; ici chaque tranche utilise la sienne
  (jusqu'à 1 € d'écart sur une pièce, 125 € sur un lingot de 1 kg).

## Confidentialité

GitHub Pages est public, donc les données (commissions, marges, revente à la fonte) sont **chiffrées** (AES-256) avec
`SITE_PASSPHRASE` avant publication : le dépôt ne contient ni règles ni tarifs en clair, et le workflow refuse de publier
sans mot de passe. Le site est aussi masqué des moteurs de recherche. Ne diffuse pas le mot de passe hors de l'agence.

## Onglets

Pièces (argent/or, rachat/vente) : colonnes comme dans les fichiers Excel (cours brut, frais, puis par tranche *COMMISSION x %* :
commission, valeur, TMP, net client), sans quantités. Bijoux : tableau « BASE » (net, revente fonte, marge, taux, valo),
grille de tous les prix possibles avec achat client, MB et % de marge selon le poids, lignes Godot/Fidso, prix libre.

## Anomalies Excel reprises à part

- AG 835 : valo/gramme à 0,68 au lieu de 0,835 (bug Excel) ; les grilles AG 835 et AG 680 s'appuient sur la revente de l'AG 925.
- Blanc/rose : la revente est celle de l'or jaune dans BASE, mais ×0,9 dans le simulateur.
- Coefficient de marge 0,8906 (et non 0,89) ; spot argent bijoux 1 200 vs 1 300 pour les pièces.

## Limites à connaître

- Les lecteurs de pages (Godot, Fidso, gold.fr, BullionVault) dépendent de la mise en page de ces sites : si l'un d'eux la change, la source passe en rouge et il faut me redonner la page.
- GitHub désactive les tâches planifiées d'un dépôt public après 60 jours sans aucune activité : si le site ne bouge plus, relance le workflow à la main.
- Ouvert depuis un fichier local (double-clic), le site ne peut pas charger les prix : utilise l'adresse GitHub Pages.
