# Grist To DS

Widget Grist qui permet d'appliquer/retirer des **labels** sur les dossiers
de **Démarches Simplifiées (DS)**, directement depuis un tableau Grist.

Ce document est écrit pour quelqu'un qui a des notions de développement
(sait lire du code, utiliser un terminal, git...) mais qui n'est pas
forcément développeur au quotidien. Le but : pouvoir reprendre ce projet
sans connaître son historique.

---

## 1. À quoi sert cette application ?

Cette application est un **petit serveur qui fait deux choses** :

1. **Servir la page du widget Grist** : Grist affiche des "widgets" dans
   des `<iframe>`. Ce widget est une page web (HTML + JavaScript) qui
   affiche, pour le dossier sélectionné dans Grist, des boutons
   "Ajouter <label>" / "Supprimer <label>".

2. **Servir de proxy (relais) vers l'API de Démarches Simplifiées** : le
   JavaScript de la page ci-dessus tourne dans le **navigateur** de
   l'utilisateur. Or l'API de Démarches Simplifiées applique une règle de
   sécurité navigateur appelée **CORS** (Cross-Origin Resource Sharing),
   qui **interdit** à une page chargée depuis un domaine (ici, notre
   widget) d'appeler directement une API sur un autre domaine
   (`www.demarches-simplifiees.fr`) si celle-ci n'autorise pas
   explicitement ce domaine.

   Notre serveur Python, lui, n'est pas un navigateur et n'est donc pas
   soumis à CORS : il peut appeler l'API de DS sans restriction. Le
   schéma est donc :

   ```
   Navigateur (widget Grist, JS)  --fetch("/create")-->  Notre serveur Python
                                                                |
                                                                v
                                                  API GraphQL Démarches Simplifiées
   ```

   C'est aussi ce serveur qui garde le **jeton secret** (`DS_TOKEN`)
   nécessaire pour s'authentifier auprès de DS : ce jeton ne doit
   **jamais** se retrouver dans le code JavaScript envoyé au navigateur,
   sinon n'importe quel visiteur pourrait l'y lire (avec l'inspecteur du
   navigateur) et l'utiliser à votre place.

---

## 2. Deux "serveurs" dans un seul projet : ne pas les confondre

C'est le point le plus important à comprendre pour se repérer dans le
code. Il y a en réalité **deux mondes différents** dans ce dépôt, qui
s'exécutent à des endroits différents :

### a) La partie serveur / back-end : [`app.py`](app.py)

- Écrite en **Python**, avec le framework **Flask**.
- S'exécute **sur le serveur** (votre machine en local, ou Scalingo en
  production) — jamais dans le navigateur de l'utilisateur.
- Définit les **routes** (les URLs auxquelles l'application répond) :
  - `GET /` → renvoie la page du widget (voir point b).
  - `POST /create` → reçoit une requête du widget et la relaie
    ("proxy") vers l'API GraphQL de Démarches Simplifiées, avec le
    jeton secret `DS_TOKEN`, puis renvoie la réponse de DS telle quelle.
- C'est le seul fichier du projet où l'on peut lire/écrire des
  variables d'environnement (`os.getenv(...)`) et faire des appels HTTP
  sortants "de confiance" (avec le token secret).

### b) La partie front / navigateur : [`templates/index.html`](templates/index.html)

- Un seul fichier contenant du **HTML + CSS + JavaScript**.
- Ce fichier est **envoyé tel quel** par `app.py` (fonction `index()`,
  via `render_template`) en réponse à `GET /`. Ensuite, c'est le
  **navigateur** (dans l'iframe du widget Grist) qui l'exécute — le
  serveur Python n'a plus rien à faire une fois la page envoyée.
- Utilise le SDK JavaScript officiel de Grist
  (`grist-plugin-api.js`, chargé depuis `docs.getgrist.com`) pour :
  - savoir sur quel dossier (quelle ligne Grist) l'utilisateur est
    positionné (`grist.onRecord`) ;
  - lire les tables Grist (labels disponibles, dossiers) via
    `grist.docApi.fetchTable(...)` ;
  - écrire dans le document Grist (mettre à jour la colonne des labels
    du dossier) via `grist.docApi.applyUserActions(...)`.
- Quand l'utilisateur clique sur un bouton "Ajouter/Supprimer un label",
  ce JavaScript appelle `fetch("/create")` — c'est-à-dire **notre
  propre serveur Python** (chemin relatif, même domaine, donc pas de
  souci CORS), qui se chargera lui-même d'appeler l'API de Démarches
  Simplifiées (voir point a).
- Utilise aussi le framework de style **DSFR** (Système de Design de
  l'État français) chargé depuis un CDN, uniquement pour l'apparence
  des boutons/messages.

**Point de jonction entre les deux mondes** : `app.py` utilise le moteur
de templates **Jinja2** (fourni par Flask) pour injecter deux valeurs
dans le HTML avant de l'envoyer au navigateur :
`{{ LABEL_TABLE }}` et `{{ DOSSIERS_TABLE }}` dans `templates/index.html`
sont remplacés par le contenu des variables d'environnement du même nom.
En dehors de ces deux valeurs, les deux mondes ne communiquent que via
les appels réseau `fetch("/create")` décrits ci-dessus.

---

## 3. Les variables d'environnement (fichier `.env`)

L'application a besoin de 4 informations de configuration, lues via
`os.getenv(...)` dans `app.py` :

| Variable          | À quoi ça sert                                                                 |
|-------------------|---------------------------------------------------------------------------------|
| `LABEL_TABLE`     | Nom de la table Grist qui contient la liste des labels et leur identifiant DS   |
| `DOSSIERS_TABLE`  | Nom de la table Grist qui contient les dossiers (synchronisés depuis DS)        |
| `DS_TOKEN`        | Jeton secret d'authentification à l'API de Démarches Simplifiées                |
| `DS_TARGET`       | URL de l'API GraphQL de Démarches Simplifiées (`.../api/v2/graphql`)            |

### `.env` vs `.env.EXEMPLE` — et pourquoi on ne copie jamais `.env`

Il y a deux fichiers qui se ressemblent, mais qui n'ont pas du tout le
même rôle :

- **[`.env.EXEMPLE`](.env.EXEMPLE)** : un fichier **modèle**, versionné
  dans git (donc visible par tout le monde ayant accès au dépôt). Il
  montre la **forme attendue** des variables, avec des commentaires
  d'explication, mais **sans aucune vraie valeur secrète**. Son seul but
  est pédagogique : "voici les variables à définir, voici ce qu'elles
  signifient".

- **`.env`** : le fichier **réel**, utilisé uniquement quand on lance
  l'application **en local sur sa machine**. Il contient les **vraies
  valeurs**, y compris le `DS_TOKEN` — un vrai secret qui donne accès à
  l'API de Démarches Simplifiées. C'est `python-dotenv`
  (`load_dotenv()` dans `app.py`) qui lit ce fichier au démarrage et
  charge son contenu comme variables d'environnement.

**Ce fichier `.env` n'est jamais envoyé sur git**, et c'est volontaire :
voir le fichier [`.gitignore`](.gitignore), qui contient la ligne
`.env`. Concrètement, git ignore totalement ce fichier : il n'apparaît
jamais dans `git status`, ne peut pas être ajouté par erreur avec
`git add`, et n'a jamais été présent dans l'historique du dépôt.

**Pourquoi c'est important** :
- Un dépôt git (surtout sur GitHub) peut être vu par d'autres personnes,
  ou fuiter. Si `DS_TOKEN` s'y trouvait, n'importe qui pourrait l'utiliser
  pour agir sur les dossiers de Démarches Simplifiées à votre place.
- Chaque personne (ou chaque environnement : local / production) peut
  avoir des valeurs différentes dans son propre `.env`, sans jamais les
  partager par erreur.

**Conséquence pratique** : quand vous récupérez ce projet pour la
première fois (`git clone`), il n'y a **pas de fichier `.env`** — c'est
normal, il faut le créer soi-même :

```bash
cp .env.EXEMPLE .env
```

puis remplacer les valeurs d'exemple par les vraies (notamment le vrai
`DS_TOKEN`, à récupérer auprès de la personne qui gère l'accès à
l'API Démarches Simplifiées, ou dans le gestionnaire de secrets de
l'équipe).

En **production sur Scalingo**, il n'y a pas non plus de fichier `.env`
sur le serveur : les mêmes 4 variables sont définies directement dans
l'interface de Scalingo (voir section 5 ci-dessous). Le code
(`os.getenv(...)`) fonctionne à l'identique dans les deux cas, seule la
manière de fournir les variables change.

---

## 4. Lancer l'application en local

Prérequis : Python 3 installé.

```bash
# 1. Installer les dépendances Python (voir requirements.txt)
pip install -r requirements.txt

# 2. Créer son fichier de configuration local à partir du modèle
cp .env.EXEMPLE .env
# puis éditer .env pour y mettre les vraies valeurs

# 3. Lancer le serveur
python app.py
```

Le serveur écoute alors en local (par défaut sur le port utilisé par
Flask). Pour le tester comme un vrai widget Grist, il faut renseigner
son URL dans la configuration d'un widget "custom" côté Grist.

Fichiers annexes utiles à connaître :
- [`requirements.txt`](requirements.txt) : liste des bibliothèques
  Python nécessaires (Flask, gunicorn, requests, dotenv).
- [`Procfile`](Procfile) : indique à Scalingo (et à des plateformes
  similaires comme Heroku) comment démarrer l'application en
  production, avec `gunicorn` (un serveur d'application Python plus
  robuste que le serveur de développement de Flask) au lieu de
  `python app.py`.

---

## 5. Mettre en ligne une modification : git push puis redéploiement sur Scalingo

Le dépôt de code est hébergé sur **GitHub**
(`https://github.com/qloridant/grist-to-ds`), mais l'application
**tourne**, elle, sur **Scalingo** (hébergeur d'applications). GitHub et
Scalingo sont deux services séparés : pousser du code sur GitHub ne met
pas automatiquement à jour l'application en ligne sur Scalingo, sauf si
un lien automatique a été configuré entre les deux. Voici la démarche
en supposant qu'il n'y a **pas** d'automatisation :

### Étape 1 — Envoyer le code sur GitHub

```bash
git status                 # vérifier ce qui a changé
git add <fichiers modifiés>
git commit -m "Description claire du changement"
git push origin main
```

### Étape 2 — Redéployer sur Scalingo

Scalingo peut être relié de deux façons différentes ; selon la
configuration de ce projet sur le tableau de bord Scalingo, utilisez
l'une des deux méthodes :

**Cas A — Déploiement automatique lié à GitHub** (le plus courant si
configuré) : Scalingo surveille la branche `main` du dépôt GitHub. Dans
ce cas, le `git push origin main` de l'étape 1 **déclenche
automatiquement** un nouveau déploiement — il suffit d'attendre quelques
minutes et de vérifier le déploiement dans l'onglet **"Deployments"** du
tableau de bord Scalingo de l'application.

**Cas B — Déploiement manuel via un remote git Scalingo** : Scalingo
fournit aussi une adresse git dédiée. Il faut alors pousser le code
**une seconde fois**, vers Scalingo cette fois :

```bash
# à faire une seule fois, pour ajouter l'adresse du remote Scalingo
# (adresse visible dans le tableau de bord Scalingo, onglet "Git" de
# l'application, ex: git@ssh.osc-fr1.scalingo.com:nom-app.git)
git remote add scalingo <adresse-git-scalingo>

# à refaire à chaque mise en ligne
git push scalingo main
```

Ce `git push scalingo main` envoie le code directement à Scalingo, qui
détecte le `Procfile` et `requirements.txt`, réinstalle les dépendances
et relance l'application avec `gunicorn` (voir `Procfile`).

**Dans les deux cas**, si vous avez besoin de forcer un redéploiement
sans avoir changé de code (par exemple après avoir modifié une variable
d'environnement dans l'interface Scalingo), vous pouvez aussi utiliser le
bouton **"Redeploy"** disponible dans le tableau de bord Scalingo,
sans avoir à repousser de code.

### Étape 3 — Vérifier / configurer les variables d'environnement sur Scalingo

Comme expliqué en section 3, le fichier `.env` n'est **jamais** envoyé
sur GitHub ni sur Scalingo. Il faut donc, **une fois par application
Scalingo** (pas à chaque déploiement), configurer manuellement les 4
variables listées en section 3 dans l'interface Scalingo : onglet
**"Environment"** (ou "Variables d'environnement") de l'application,
en utilisant les mêmes noms de clés que dans `.env.EXEMPLE`
(`LABEL_TABLE`, `DOSSIERS_TABLE`, `DS_TOKEN`, `DS_TARGET`).

Si une de ces variables est absente, l'application affichera une erreur
explicite (ex : `❌ DS_TOKEN manquant`) au lieu de planter silencieusement
— voir la fonction `index()` dans `app.py`.

---

## 6. Résumé visuel

```
                     ┌─────────────────────────────────────────┐
                     │      Navigateur (widget dans Grist)      │
                     │   templates/index.html (HTML + JS)       │
                     │   - lit/écrit les tables Grist            │
                     │   - fetch("/create") pour agir sur DS    │
                     └───────────────────┬───────────────────────┘
                                          │ HTTP (même domaine, pas de CORS)
                                          v
                     ┌─────────────────────────────────────────┐
                     │        Serveur Python (app.py)           │
                     │   GET  /        -> sert index.html        │
                     │   POST /create  -> proxy vers l'API DS    │
                     │   (garde le DS_TOKEN secret)              │
                     └───────────────────┬───────────────────────┘
                                          │ HTTP (le serveur n'a pas de CORS)
                                          v
                     ┌─────────────────────────────────────────┐
                     │   API GraphQL Démarches Simplifiées       │
                     └─────────────────────────────────────────┘
```
