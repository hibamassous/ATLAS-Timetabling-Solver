# ATLAS Timetabling Solver

**Affectation automatique des salles aux emplois du temps — Université Mohammed V, Rabat**

Application de bureau (Python / Tkinter) qui affecte une salle à chaque séance de cours à l'aide
d'un **algorithme génétique**. Les jours et horaires sont fixés par le fichier Excel et ne sont
jamais modifiés : seule la salle est calculée.

Fonctionnalités : comptes utilisateurs (administrateur / responsable), instances de travail,
exécution de l'algorithme en lot (plusieurs runs), grille d'occupation par salle, emploi du temps
par filière, vérification des contraintes, courbes de fitness, réaffectation manuelle,
gestion des salles et exports Excel.

## Fichiers du dépôt

| Fichier | Rôle |
|---|---|
| `ATLAS_Timetabling_Solver.py` | Interface graphique Tkinter (**point d'entrée**) |
| `engine.py` | Moteur : lecture Excel, pilotage de l'algorithme (thread), gestion des cours, export Excel |
| `allocator.py` | Algorithme génétique (`EvolutionaryAllocator`), salles, contraintes |
| `run_30_experiments.py` | Script de 30 exécutions indépendantes (sans interface) |
| `rooms_config.json` | Catalogue des salles utilisé par l'application (75 salles) |
| `salles.xlsx` | Fichier de salles importable depuis l'application (75 salles) |
| `200_EDT_v1.xlsx` | Jeu de données : 200 emplois du temps, 1200 séances |
| `results_30_runs.json`, `summary_30_runs.json` | Résultats des 30 exécutions (voir la note plus bas) |
| `requirements.txt` | Dépendances Python |

## Installation

Python 3.9 ou plus récent. Tkinter est fourni avec Python sous Windows et macOS
(Linux : `sudo apt install python3-tk`).

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt
```

## Lancement

```bash
python ATLAS_Timetabling_Solver.py
```

L'interface est conçue pour **Windows** (barre de titre bleue via `ctypes`).

## Comptes utilisateurs

| Identifiant | Mot de passe | Rôle |
|---|---|---|
| `admin` | `Admin@2026` | Administrateur |
| `responsable` | `Salles@2026` | Responsable des salles |

Définis dans le dictionnaire `USERS` (mots de passe hachés avec `werkzeug`). Changez-les avant
tout usage réel.

| Fonction | Administrateur | Responsable |
|---|:-:|:-:|
| Charger les cours, lancer l'algorithme, exporter, réaffecter une salle | ✅ | ✅ |
| Importer des salles (Excel), session vide | ✅ | ❌ |
| Ajouter / modifier / supprimer cours et salles | ✅ | ❌ (lecture seule) |

## Utilisation

1. **Charger les cours** (`📥 Load courses`) : par exemple `200_EDT_v1.xlsx`.
2. **Choisir l'instance** (`🎯 WORKING INSTANCE`) : tous les cours, un lot de 25 EDT, un EDT seul,
   ou une instance de **N cours** (les N premiers, ou N tirés au hasard avec « Random »).
3. **Régler les paramètres** :

   | Paramètre | Défaut | Bornes |
   |---|---|---|
   | Population | 60 | 10 – 400 |
   | Generations | 300 | 10 – 3000 |
   | Crossover | 0.8 | 0 – 1 |
   | Mutation | 0.05 | 0 – 1 |
   | Seed (vide = aléatoire) | 42 | entier |
   | Runs per click | 30 | 1 – 1000 |

4. **Lancer** (`▶️ Run GA`) : l'algorithme est exécuté *Runs per click* fois (graines `seed`,
   `seed+1`, …) dans un thread séparé, avec progression et journal en direct. `⏹️ Stop`
   interrompt le lot.
5. **Consulter** les onglets :

   | Onglet | Contenu |
   |---|---|
   | 📅 ROOM OCCUPANCY | Grille salle × heure par jour (filtres salle / filière). Un clic sur un cours ouvre la réaffectation (capacité et conflits vérifiés). |
   | 📚 TIMETABLE (PROGRAM) | Emploi du temps hebdomadaire d'un EDT avec les salles. |
   | 📋 DETAILED LIST | Liste complète des cours (édition réservée à l'administrateur). |
   | 📊 STATISTICS | Contraintes dures et souples, conflits de professeurs, fitness, variance, écart-type, temps. |
   | 📈 FITNESS EVOLUTION | Courbe de chaque run et courbe moyenne. |
   | 🏢 ROOM MANAGEMENT | Catalogue des salles. |

6. **Exporter** : `📅 Export timetable`, `🏢 Export rooms`, `📋 Export details` (fichiers `.xlsx`).

## Algorithme génétique (`allocator.py`)

Chaque individu associe une salle à chaque séance. Valeurs par défaut du module (surchargées par
l'interface) : sélection par tournoi (taille 3), élitisme de 2 individus, pénalités de capacité
(40), de conflit d'enseignant (20) et de répartition des groupes (10). Après convergence, une
étape de réparation locale réaffecte les séances encore en dépassement de capacité vers une salle
libre assez grande. L'arrêt peut survenir avant le nombre maximal de générations si le fitness
stagne.

## Contraintes vérifiées (onglet Statistics)

**Dures** : capacité ≥ effectif ; pas de chevauchement dans une même salle ; pas de chevauchement
pour un même groupe (EDT) ; disponibilité des professeurs.

**Souples** : toutes les séances ont une salle ; salle bien dimensionnée (capacité ≤ 2 × effectif) ;
peu de changements de salle dans la journée pour un même EDT.

Les conflits de professeurs viennent des **données sources** (horaires non modifiés) : ils sont
listés pour corriger le fichier Excel.

## Format du fichier de cours

Une ligne d'en-tête est détectée automatiquement parmi les 10 premières lignes ; seuls les
**intitulés** comptent (insensible aux accents et aux majuscules), pas l'ordre des colonnes :

| Rôle | Intitulés reconnus |
|---|---|
| N° EDT / groupe | `EDT`, `Groupe`, `Group` |
| Filière | `Filière`, `Spécialité`, `Parcours` |
| Module | `Module`, `Cours`, `Matière`, `Subject` |
| Professeur | `Professeur`, `Prof`, `Enseignant`, `Teacher` |
| Jour | `Jour`, `Day` |
| Horaire | `Horaire`, `Heure`, `Créneau`, `Time` |
| Effectif | `Effectif`, `Students`, `Nb étudiants` |

Les horaires acceptent `10:00 – 13:00`, `8h-11h`, `8:00 à 11:00`… Plage autorisée : **8 h – 19 h**,
du lundi au samedi. Aucune colonne « salle » : c'est le résultat du calcul.

## Format du fichier de salles

`🏢 Load rooms` (administrateur) **remplace** le catalogue. Colonnes : `Lieu | Type | Numéro | Capacité`
(nom de salle = « Lieu Type Numéro », ex. `ENS Amphi 1`) ou `Nom | Capacité`. La catégorie
(amphi / moyenne / petite) est déduite du type ; à défaut, « moyenne » à partir de 60 places.
Le catalogue est enregistré dans `rooms_config.json`.

## Expériences (30 exécutions)

```bash
python run_30_experiments.py                 # utilise 200_EDT_v1.xlsx
python run_30_experiments.py mon_fichier.xlsx
```

Paramètres : population 60, 300 générations, croisement 0.8, mutation 0.05, graines 1001 à 1030.
Produit `results_30_runs.json` et `summary_30_runs.json` (moyenne, écart-type, min, max, médiane)
et écrit `progress.json` pendant l'exécution.

Résultats obtenus avec le code actuel (1200 séances, **75 salles exactement**, sans salle de réserve) :

| Indicateur | Moyenne | Écart-type | Min | Max |
|---|---|---|---|---|
| Fitness final | 118160.0 | 52.8 | 118037.5 | 118292.5 |
| Dépassements de capacité | 0 | 0 | 0 | 0 |
| Temps d'exécution (s) | 26.0 | 0.3 | 25.4 | 26.5 |
| Générations exécutées | 152 | 0 | 152 | 152 |
| Salles utilisées | 75 | 0 | 75 | 75 |

Durée totale des 30 runs : 780 s.

## Notes techniques

- Les résultats sont conservés en mémoire pendant la session : pensez à exporter avant de fermer.
- Si `rooms_config.json` est absent, un catalogue par défaut de 24 salles est créé par `allocator.py`.
- Si le nombre de séances simultanées dépasse le nombre de salles de capacité suffisante, certaines
  séances restent sans salle ou en dépassement (visible dans Statistics) : agrandissez le catalogue.
