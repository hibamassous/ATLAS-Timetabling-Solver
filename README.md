# ATLAS Timetabling Solver
![logo](img/logo.png)

**ATLAS Timetabling Solver** is a desktop application (Python / Tkinter) that automates the **room-assignment stage of university course timetabling** with a **genetic algorithm (GA)**. Days and time slots are fixed by an Excel file and never modified: only the room of each session is computed. Developed at ENS and ENSIAS, Mohammed V University, Rabat (Morocco).

## Table of Contents

- [1. Motivation and significance](#1-motivation-and-significance)
  - [1.1 Problem context](#11-problem-context)
  - [1.2 Related work](#12-related-work)
  - [1.3 Significance and contributions](#13-significance-and-contributions)
- [2. ATLAS Timetabling Solver description](#2-atlas-timetabling-solver-description)
  - [2.1 Architecture](#21-architecture)
  - [2.2 Input data and data model](#22-input-data-and-data-model)
  - [2.3 Optimisation model](#23-optimisation-model)
  - [2.4 Genetic algorithm engine](#24-genetic-algorithm-engine)
  - [2.5 Functionalities](#25-functionalities)
- [3. Getting started](#3-getting-started)
- [4. Illustrative examples](#4-illustrative-examples)
- [5. Experimental evaluation](#5-experimental-evaluation)
- [6. Impact](#6-impact)
  - [6.1 Threats to validity](#61-threats-to-validity)
  - [6.2 Limitations](#62-limitations)
- [7. Conclusions and future work](#7-conclusions-and-future-work)
- [Folder structure](#folder-structure)
- [Dependencies](#dependencies)
- [Citation](#citation)
- [Contributors](#contributors)

---

## 1. Motivation and significance

### 1.1 Problem context

Assigning rooms to hundreds of weekly sessions by hand, while respecting capacities and avoiding simultaneous use of a room, is slow and error-prone. This work focuses on university course timetabling where the **day and time slot of each session are fixed** and the objective is to assign a suitable room to each session (capacity, no simultaneous use, and, where applicable, teacher availability and room-type requirements). Genetic algorithms suit this combinatorial, highly constrained problem: they explore large search spaces and merge several criteria into one fitness function.

### 1.2 Related work

Educational timetabling (school, university course, examination) is NP-hard; heuristics and metaheuristics (genetic algorithms, simulated annealing, tabu search) are widely used. Most studies focus on the algorithm rather than on the complete software environment. Tools such as FET, UniTime or Timefold/OptaPlanner address timetabling more broadly through generic constraint models or server-side deployments; ATLAS targets the room-assignment stage with a **lightweight, locally executed interface**.

### 1.3 Significance and contributions

- a single weighted fitness function (capacity, room-time overlap, teacher, room type, group load, bonuses for preferred rooms and room diversity);
- two post-convergence repair procedures (capacity and room-time overlap) that do not modify the evolutionary loop;
- a GUI with Excel import (automatic column detection), working-instance selection, GA configuration, real-time monitoring, course and room management and Excel export;
- validated manual re-assignment and a hard-constraint verification panel;
- a thread/queue architecture that keeps the interface responsive.

## 2. ATLAS Timetabling Solver description

### 2.1 Architecture

![archi](img/architecture.png)

All computation is local (no server, no database). The GA runs in a **background thread**; progress (generation, best fitness, stagnation, run number, log) is sent to the GUI through a **thread-safe queue** polled by the main thread. The *Stop* button sets a flag read between two generations.

| Component | Main responsibility |
|---|---|
| `ATLAS_Timetabling_Solver.py` | Tkinter GUI (**entry point**): login, tabs, grid rendering, constraint checker, run orchestration |
| `engine.py` | Excel parsing, `Moteur` (background GA runner), progress reporting, Excel export |
| `allocator.py` | Domain model (`Course`, `Room`, `ConstraintManager`) and GA `EvolutionaryAllocator` with repairs |
| `rooms_config.json` | Editable catalogue of 75 rooms (68 ENS + 7 Annexe) |

### 2.2 Input data and data model

**Courses.** One Excel row per weekly session: EDT number, programme (*Filière*), module, teacher, day, time interval, number of students. The header row is detected automatically among the first 10 rows; only the **column titles** matter (case- and accent-insensitive):

| Role | Recognised titles |
|---|---|
| EDT / group | `EDT`, `Groupe`, `Group` |
| Programme | `Filière`, `Spécialité`, `Parcours` |
| Module | `Module`, `Cours`, `Matière`, `Subject` |
| Teacher | `Professeur`, `Prof`, `Enseignant`, `Teacher` |
| Day | `Jour`, `Day` |
| Time | `Horaire`, `Heure`, `Créneau`, `Time` |
| Students | `Effectif`, `Students`, `Nb étudiants` |

Accepted time formats: `10:00 – 13:00`, `8h-11h`, `8:00 à 11:00`. Allowed range: 8:00–19:00, Monday to Saturday. There is no room column: the room is the result.

![excel](img/fig_excel_input.jpg)

**Rooms.** `🏢 Load rooms` (administrator) **replaces** the catalogue. Columns: `Lieu | Type | Numéro | Capacité` (name = "Lieu Type Numéro", e.g. `ENS Amphi 1`) or `Nom | Capacité`. Saved in `rooms_config.json`. If it is missing, a default catalogue of 24 rooms is created by `allocator.py`.

![rooms](img/fig_salles_excel.jpg)

| Category | Count | Capacity range | Campus |
|---|--:|---|---|
| ENS amphitheatres | 18 | 60–120 | ENS |
| ENS classrooms | 50 | 40–90 | ENS |
| Annexe amphitheatres | 2 | 100–120 | Annexe |
| Annexe classrooms | 5 | 35–70 | Annexe |
| **Total** | **75** | | |

**Data model.** `Course` (group, programme, module, teacher, day, start/end, students, priority); `Room` (name, type, capacity, features, campus); `ConstraintManager` (teacher availability, room preferences/exclusions, required room types); `EvolutionaryAllocator` receives them and produces one room per course.

### 2.3 Optimisation model

The decision variable is `x_i ∈ R`, the room of session *i* (one room per session by construction). The fitness to maximise is

```
F(x) = max(0, 100·n − P(x) + B(x))
```

with `P` the weighted penalty and `B` the bonus.

| Term | Weight |
|---|---|
| Capacity overbooking | 40 × missing seats |
| Disallowed room | 50 (flat) |
| Teacher unavailable | 20 |
| Missing feature | 10 / missing |
| Room-type mismatch | 30 |
| Room-time overlap | 25 / pair |
| Group overload per day | 10 × excess |
| Teacher > 4 sessions/day | 5 × excess |
| Gross over-capacity (> 3×) | 5 (flat) |
| Preferred room | +10 |
| Priority > 5 | + priority / 2 |
| Room diversity | +0.5 / room + 15·ρ (ρ = share of catalogue used) |

The `100·n` baseline makes `F/n` comparable across instance sizes. The search space has `m^n` elements (about 10^169, 10^338, 10^450 for n = 90, 180, 240 with m = 75), which motivates a population-based GA.

### 2.4 Genetic algorithm engine

- **Chromosome**: vector of room indices, one per session.
- **Initialisation**: suitable rooms (capacity, teacher availability, type) are preferred.
- **Selection**: tournament (k = 3). **Elitism**: 2 individuals.
- **Crossover**: multi-point (1 to 3 points), probability `pc`.
- **Mutation**: gene-wise, probability `pm`; new room drawn among suitable rooms with probability 0.7, otherwise uniformly.
- **Early stopping**: after 50 % of the budget, if no improvement during the last 30 % of generations and no residual capacity overbooking.
- **Post-convergence repair** (once): (1) over-capacity sessions are moved to the *smallest* sufficient free room; (2) sessions still in a room-time overlap are moved to a suitable free room at the same slot.

### 2.5 Functionalities

**Accounts (development version).** In-memory `USERS` dictionary, passwords hashed with `werkzeug`. Change them before real use.

| Login | Password | Role |
|---|---|---|
| `admin` | `Admin@2026` | Administrator |
| `responsable` | `Salles@2026` | Room manager |

| Function | Administrator | Room manager |
|---|:-:|:-:|
| Load courses, run GA, export, re-assign a room | ✅ | ✅ |
| Import rooms (Excel), empty session | ✅ | ❌ |
| Add / edit / delete courses and rooms | ✅ | ❌ (read-only) |

**Workflow.** (1) Sign in → (2) Load courses (`📥 Load courses`) and optionally rooms → (3) Choose the working instance (`🎯 WORKING INSTANCE`: all courses, 25-EDT batch, single EDT, or *N* courses, first or random) → (4) Set GA parameters → (5) `▶️ Run GA` (`⏹️ Stop` keeps the best solution so far) → (6) Inspect results → (7) Adjust manually → (8) Export.

| Parameter | Default | Range |
|---|---|---|
| Population | 60 | 10 – 400 |
| Generations | 300 | 10 – 3000 |
| Crossover | 0.8 | 0 – 1 |
| Mutation | 0.05 | 0 – 1 |
| Seed (empty = random) | 42 | integer |
| Runs per click | 30 | 1 – 1000 |

Runs use seeds `seed`, `seed+1`, …

![dashboard](img/ui_main_window.jpg)

**Tabs.**

| Tab | Content |
|---|---|
| 📅 ROOM OCCUPANCY | Room × hour grid per day (room / programme filters). Click a course to re-assign it (capacity and overlap checked). |
| 📚 TIMETABLE (PROGRAM) | Weekly timetable of one EDT with rooms. |
| 📋 DETAILED LIST | All courses (editing reserved to the administrator). |
| 📊 STATISTICS | Constraints, teacher conflicts, fitness, variance, standard deviation, time. |
| 📈 FITNESS EVOLUTION | Curve of each run and average curve. |
| 🏢 ROOM MANAGEMENT | Room catalogue. |

**Hard-constraint verification panel.** Four hard constraints are checked: room capacity, room/time-slot overlap, group (EDT) overlap, professor availability. Soft constraints: every session has a room, room well sized (capacity ≤ 2 × students), few room changes per day for one EDT. Teacher conflicts come from the **source data** (times are not modified) and are listed so the Excel file can be corrected.

**Export.** `📅 Export timetable`, `🏢 Export rooms`, `📋 Export details` (`.xlsx`). Results live in memory only: **export before closing**.

## 3. Getting started

Requirements: Python 3.9+, Tkinter (included on Windows/macOS; Linux: `sudo apt install python3-tk`). The interface is designed for **Windows**.

```bash
git clone <repository_url>
cd <project_folder>
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python ATLAS_Timetabling_Solver.py
```

## 4. Illustrative examples

**Example 1 – Loading data and running the allocation.** The administrator signs in, loads `200_EDT_v1.xlsx`, creates an instance, sets the parameters and clicks Run GA (30 runs, best solution retained).

![login](img/ui_login.jpg)

**Example 2 – Reviewing the timetable of a group.** `EDT_001 — Mathématiques S2` (180-session run): six sessions from Monday to Saturday with their rooms.

![timetable](img/tt_180.jpg)

**Example 3 – Auditing room occupancy.** Monday, 180-session run: 35 courses, 24/75 rooms used, 0 overlapping sessions.

![occupancy](img/occ_180.jpg)

**Example 4 – Manual room change.** Click an occupied cell and choose another room; capacity and overlap are re-validated and unsuitable rooms are rejected with an explicit message.

## 5. Experimental evaluation

Parameters: population 60, 300 generations, pc = 0.8, pm = 0.05, seed 42, 30 runs per instance, 75-room catalogue, first 90, 180 and 240 sessions of `200_EDT_v1.xlsx` (200 EDT, 1200 sessions).

| Metric | 90 sessions | 180 sessions | 240 sessions |
|---|--:|--:|--:|
| Timetables (EDT) | 15 | 30 | 40 |
| Sessions allocated | 90/90 | 180/180 | 240/240 |
| Rooms used | 61/75 | 68/75 | 63/75 |
| Best fitness (panel) | 9 042.7 | 18 047.6 | 24 039.1 |
| Fitness std. dev. | 3.894 | 3.174 | 1.884 |
| Time, 30 runs (s) | 313.76 | 687.90 | 762.53 |
| Mean time per run (s) | 10.46 | 22.93 | 25.42 |
| Mean generations per run | 281.8 | 284.3 | 198.2 |
| Time per generation (s) | 0.037 | 0.081 | 0.128 |
| Hard constraints satisfied | 4/4 | 4/4 | 4/4 |

![stats90](img/stats_90.jpg)
![fit90](img/fit_90.jpg)

**Full dataset (1200 sessions)**, `run_30_experiments.py`, seeds 1001–1030:

| Indicator | Mean | Std. dev. | Min | Max |
|---|--:|--:|--:|--:|
| Final fitness | 118160.0 | 52.8 | 118037.5 | 118292.5 |
| Capacity overbookings | 0 | 0 | 0 | 0 |
| Execution time (s) | 26.0 | 0.3 | 25.4 | 26.5 |
| Generations executed | 152 | 0 | 152 | 152 |
| Rooms used | 75 | 0 | 75 | 75 |

```bash
python run_30_experiments.py                 # uses 200_EDT_v1.xlsx
python run_30_experiments.py my_file.xlsx
```

Outputs: `results_30_runs.json`, `summary_30_runs.json`, and `progress.json` during execution.

## 6. Impact

ATLAS is intended for timetable and room managers (ENS, Mohammed V University), and as a reusable open-source base (Excel in/out, editable catalogue, documented GA engine) for researchers testing new operators or constraints. A complete allocation of 240 sessions takes about 25 s per run; a batch of 30 runs takes 5 to 13 minutes. The manual re-assignment keeps the human in control: the algorithm proposes, the manager corrects, and any correction creating a capacity or overlap violation is refused.

### 6.1 Threats to validity

- **Internal**: a single batch seed (42); gains read graphically from charts.
- **Construct**: the diversity bonus explains almost all of the fitness gain; the hard-constraint panel is needed to confirm feasibility.
- **External**: first-*n* subsets of one partly synthetic dataset, lightly loaded relative to the 75 rooms.
- **Conclusion**: descriptive comparison only, no statistical test.

### 6.2 Limitations

- Room assignment only: days and time slots are inputs.
- Penalty weights are code-level constants (no sensitivity analysis).
- No greedy or exact baseline; hard constraints documented on the displayed solution only, not aggregated over the 30 runs.
- Results are in memory only; hard-coded development credentials; no automated tests or CI.
- If simultaneous sessions exceed the number of rooms with enough capacity, some sessions stay unassigned or over capacity (visible in Statistics): enlarge the catalogue.

## 7. Conclusions and future work

ATLAS allocated all sessions of the three instances (90, 180, 240) with mean times per run of 10.5, 22.9 and 25.4 s, and 4/4 hard constraints satisfied. Future work: larger and denser instances (full 1200 sessions), systematic verification on every run, a baseline comparison, a sensitivity analysis of the penalty weights, joint room and time-slot optimisation, search improvements, persistent storage with production-grade authentication and tests, and validation on independently collected timetables.

## Folder structure

```
.
├── ATLAS_Timetabling_Solver.py   # Tkinter GUI (entry point)
├── engine.py                     # Excel reading, GA runner (thread), Excel export
├── allocator.py                  # Genetic algorithm, rooms, constraints
├── run_30_experiments.py         # 30 independent runs, no GUI
├── rooms_config.json             # Room catalogue (75 rooms)
├── salles.xlsx                   # Importable room file (75 rooms)
├── 200_EDT_v1.xlsx               # Dataset: 200 timetables, 1200 sessions
├── results_30_runs.json
├── summary_30_runs.json
├── requirements.txt
└── img/                          # Screenshots and figures
```

## Dependencies

`pip install -r requirements.txt`. Main libraries: **pandas**, **openpyxl**, **matplotlib**, **werkzeug**, and **Tkinter** (standard distribution).

## Citation

> N. El Machichi, F. Kharroubi, H. Massous, S. Ouali, A. El Youssfi, "Genetic Algorithm-Based University Course Timetabling: A Practical Optimization Framework with Graphical Interface," *International Journal of Computer Engineering and Data Science (IJCEDS)*, vol. 5, no. 2, pp. 9–25, 2026.

## Contributors

- Fouad Kharroubi ([ResearchGate](https://www.researchgate.net/profile/Fouad-Kharroubi)) — ENSIAS, Mohammed V University
- Hiba Massous ([ResearchGate](https://www.researchgate.net/profile/Hiba-Massous)) — ENS, Mohammed V University
- Mohamed Lachgar ([ResearchGate](https://www.researchgate.net/profile/Mohamed-Lachgar)) — ENS, Cadi Ayyad University
- Nouhaila El Machichi ([ResearchGate](https://www.researchgate.net/profile/Nouhaila-El-Machichi-2)) — ENS, Mohammed V University


Contact: fouad.kharroubi@gmail.com
