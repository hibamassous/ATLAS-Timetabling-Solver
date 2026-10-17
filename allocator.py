# -*- coding: utf-8 -*-
"""
Core domain logic for the room-allocation genetic algorithm.

This module is a GUI-free port of the original Tkinter desktop tool:
Room / Course / ConstraintManager / EvolutionaryAllocator are unchanged in
behaviour, so the same course timetables and room catalogues produce the
same allocations. Everything here is plain Python + pandas/openpyxl so it
can run headless behind a Flask API.
"""

import json
import os
import re
import random
import statistics

import pandas as pd

# ============================================
# GA DEFAULTS
# ============================================
DEFAULT_POPULATION_SIZE = 150
DEFAULT_NUMBER_GENERATIONS = 300
DEFAULT_MUTATION_RATE = 0.1
DEFAULT_TOURNAMENT_SIZE = 3
DEFAULT_ELITISM_COUNT = 2
DEFAULT_CAPACITY_PENALTY = 40
DEFAULT_TEACHER_CONFLICT_PENALTY = 20
DEFAULT_GROUP_DISTRIBUTION_PENALTY = 10

WEEK_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
              'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

DEFAULT_INSTITUTION_LOCATION = "FSAC"

# ============================================
# ROOM CATALOGUE (seed data, editable afterwards)
# ============================================
SALLES_AMPHI = ["Amphi 1", "Amphi 2", "Amphi 3", "Amphi 4", "Amphi 5",
                "Amphi 6", "Amphi 7", "Amphi 8", "Amphi 9"]
SALLES_MOYENNE = ["Salle 3", "Salle 6", "Salle 8", "Salle 10", "Salle 14"]
SALLES_PETITE = ["Salle 2", "Salle 13", "Salle 15", "Salle 16",
                  "Salle 17", "Salle 18", "Salle 19", "Salle 20", "geo", "audio"]
SALLES_ALL = SALLES_AMPHI + SALLES_MOYENNE + SALLES_PETITE

CAPACITES = {
    "Amphi 1": 400, "Amphi 2": 400, "Amphi 3": 400, "Amphi 4": 300,
    "Amphi 5": 300, "Amphi 6": 200, "Amphi 7": 200, "Amphi 8": 150, "Amphi 9": 150,
    "Salle 3": 100, "Salle 6": 100, "Salle 8": 80, "Salle 10": 80, "Salle 14": 60,
    "Salle 2": 50, "Salle 13": 50, "Salle 15": 40, "Salle 16": 40,
    "Salle 17": 35, "Salle 18": 35, "Salle 19": 40, "Salle 20": 40,
    "geo": 30, "audio": 30,
}

ROOMS_CONFIG_FILENAME = "rooms_config.json"


def _room_type_of(name):
    if name in SALLES_AMPHI:
        return "Amphi"
    if name in SALLES_MOYENNE:
        return "Salle moyenne"
    if name in ("geo", "audio"):
        return "Salle specialisee"
    return "Salle petite"


def build_default_rooms(location=DEFAULT_INSTITUTION_LOCATION):
    rooms = []
    for name in SALLES_ALL:
        rtype = _room_type_of(name)
        cap = CAPACITES.get(name, 30)
        room = Room(location, rtype, name, cap, room_id=name)
        room.name = name
        if rtype == "Amphi":
            room.add_feature("Video-projecteur")
        if name in ("geo", "audio"):
            room.add_feature("Equipement specialise")
        rooms.append(room)
    rooms.sort(key=lambda r: -r.capacity)
    return rooms


def rooms_config_path(base_dir=None):
    base = base_dir or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, ROOMS_CONFIG_FILENAME)


def _category_of(room_type):
    t = str(room_type).lower()
    if t == "amphi":
        return "amphi"
    if "moyenne" in t:
        return "moyenne"
    return "petite"


def rooms_to_payload(rooms):
    return [
        {
            "name": r.name, "type": r.type, "category": _category_of(r.type),
            "capacity": r.capacity, "location": r.location,
            "features": list(r.features),
        }
        for r in rooms
    ]


def payload_to_rooms(payload):
    rooms = []
    for item in payload:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        rtype = str(item.get("type", "Salle")).strip() or "Salle"
        cap = item.get("capacity", 30)
        loc = str(item.get("location", DEFAULT_INSTITUTION_LOCATION)).strip() or DEFAULT_INSTITUTION_LOCATION
        room = Room(loc, rtype, name, cap, room_id=name)
        room.name = name
        for feat in (item.get("features") or []):
            room.add_feature(feat)
        rooms.append(room)
    return rooms


def save_rooms_config(path, rooms):
    payload = rooms_to_payload(rooms)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def load_or_init_rooms(path=None):
    path = path or rooms_config_path()
    if not os.path.exists(path):
        try:
            save_rooms_config(path, build_default_rooms())
        except Exception:
            pass
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        rooms = payload_to_rooms(payload)
        if not rooms:
            raise ValueError("Empty rooms configuration")
        return rooms
    except Exception:
        rooms = build_default_rooms()
        try:
            save_rooms_config(path, rooms)
        except Exception:
            pass
        return rooms


# ============================================
# GESTION DES SALLES (administration)
# ============================================
_CATEGORY_TO_TYPE = {
    "amphi": "Amphi",
    "moyenne": "Salle moyenne",
    "petite": "Salle petite",
}


def list_rooms_payload(path=None):
    """Retourne la liste courante des salles (config modifiable par l'admin)."""
    return rooms_to_payload(load_or_init_rooms(path))


def upsert_room(payload, path=None):
    """Ajoute une salle, ou met a jour une salle existante (meme nom,
    insensible a la casse). Retourne la liste complete mise a jour."""
    path = path or rooms_config_path()
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("The room name is required.")

    category = str(payload.get("category", "petite")).strip().lower()
    type_label = _CATEGORY_TO_TYPE.get(category, "Salle petite")

    try:
        capacity = int(float(payload.get("capacity", 30)))
    except (TypeError, ValueError):
        raise ValueError("Invalid capacity.")
    if capacity <= 0:
        raise ValueError("Capacity must be a positive number.")

    features = payload.get("features") or []
    if isinstance(features, str):
        features = [f.strip() for f in features.split(",") if f.strip()]

    rooms = load_or_init_rooms(path)
    rooms = [r for r in rooms if r.name.strip().lower() != name.lower()]
    location = str(payload.get("location") or "").strip() or DEFAULT_INSTITUTION_LOCATION
    room = Room(location, type_label, name, capacity, room_id=name)
    room.name = name
    for feat in features:
        room.add_feature(feat)
    rooms.append(room)
    rooms.sort(key=lambda r: -r.capacity)
    save_rooms_config(path, rooms)
    return rooms_to_payload(rooms)


def remove_room(name, path=None):
    """Supprime une salle du catalogue. Retourne la liste complete mise a jour."""
    path = path or rooms_config_path()
    rooms = load_or_init_rooms(path)
    remaining = [r for r in rooms if r.name != name]
    if len(remaining) == len(rooms):
        raise ValueError("Room not found.")
    save_rooms_config(path, remaining)
    return rooms_to_payload(remaining)


# ============================================
# CONSTRAINT MANAGER
# ============================================
_UNKNOWN_TEACHER_LABELS = {"tbd", "n/a", "na", "unknown", "-", ""}


def is_known_teacher(teacher):
    """A placeholder teacher label (e.g. 'TBD', empty) means no professor was
    actually specified for that session in the source data. Such sessions
    must NOT be treated as if they all shared one real professor — doing so
    would create massive, entirely artificial teacher-availability and
    daily-load violations by lumping unrelated sessions under one fake
    'teacher'."""
    return str(teacher).strip().lower() not in _UNKNOWN_TEACHER_LABELS


class ConstraintManager:
    def __init__(self):
        self.teacher_constraints = {}
        self.room_preferences = {}
        self.group_distribution = {}
        self.room_exclusions = {}
        self.course_type_constraints = {}

    def add_teacher_unavailability(self, teacher, day, start_hour, end_hour, reason="Unavailable"):
        self.teacher_constraints.setdefault(teacher, []).append(
            {'day': day, 'start': start_hour, 'end': end_hour, 'reason': reason})

    def add_room_preference(self, course_id, preferred_rooms):
        self.room_preferences[course_id] = preferred_rooms

    def add_group_distribution(self, group, max_courses_per_day):
        self.group_distribution[group] = max_courses_per_day

    def add_room_exclusion(self, room_id, excluded_course_ids):
        self.room_exclusions[room_id] = excluded_course_ids

    def add_course_type_constraint(self, course_type, required_room_type):
        self.course_type_constraints[course_type] = required_room_type

    def is_teacher_available(self, teacher, day, start, end):
        if not is_known_teacher(teacher):
            # No real professor identified for this session: never treated
            # as a conflict source (see is_known_teacher()).
            return True
        if teacher not in self.teacher_constraints:
            return True
        for c in self.teacher_constraints[teacher]:
            if c['day'] == day and not (end <= c['start'] or start >= c['end']):
                return False
        return True

    def get_room_preference_bonus(self, course, room):
        if course.id in self.room_preferences and room.id in self.room_preferences[course.id]:
            return 10
        return 0

    def is_room_allowed_for_course(self, room, course):
        if room.id in self.room_exclusions and course.id in self.room_exclusions[room.id]:
            return False
        return True

    def get_required_room_type(self, course):
        for course_type, room_type in self.course_type_constraints.items():
            if course_type in course.course_name.upper():
                return room_type
        return None



# ============================================
# ROOM
# ============================================
class Room:
    def __init__(self, location, room_type, number, capacity, room_id=None):
        self.location = str(location).strip()
        self.type = str(room_type).strip()
        self.number = str(number).strip()
        try:
            self.capacity = int(float(capacity)) if pd.notna(capacity) else 0
        except (ValueError, TypeError):
            self.capacity = 0
        self.id = room_id or f"{self.location}_{self.type}_{self.number}"
        self.name = f"{self.location} - {self.type} {self.number}"
        self.features = []

    def __str__(self):
        return self.name

    def add_feature(self, feature):
        if feature and feature not in self.features:
            self.features.append(feature)

    def has_feature(self, feature):
        return feature in self.features

    def to_dict(self):
        return {"id": self.id, "name": self.name, "type": self.type,
                "capacity": self.capacity, "location": self.location,
                "features": list(self.features)}


# ============================================
# COURSE
# ============================================
class Course:
    def __init__(self, group, day, time_slot, course_name, students, course_id=None):
        self.group = str(group).strip()
        self.day = str(day).strip()
        self.time_slot = str(time_slot).strip()
        self.course_name = str(course_name).strip()
        try:
            self.students = int(float(students)) if pd.notna(students) else 0
        except (ValueError, TypeError):
            self.students = 0
        self.id = course_id or f"{self.group}_{self.course_name}_{self.day}_{self.time_slot}"
        self.assigned_room = None
        self.assigned_room_id = None

        self._parse_course_name(self.course_name)

        if "_" in self.group:
            parts = self.group.split("_")
            self.main_group = parts[0]
            self.sub_group = parts[1] if len(parts) > 1 else ""
        else:
            self.main_group = self.group
            self.sub_group = ""

        self.track = re.sub(r'[\s_\-]*\d+.*$', '', self.main_group).strip() or self.main_group

        self.start, self.end = self._convert_time(self.time_slot)
        self.duration = self.end - self.start

        self.required_features = []
        self.priority = 1
        self.course_type = self._detect_course_type()

    def _parse_course_name(self, course_name):
        if " - " in course_name:
            p = course_name.split(" - ")
            self.subject, self.teacher = p[0].strip(), (p[1].strip() if len(p) > 1 else "TBD")
        elif " (" in course_name and ")" in course_name:
            p = course_name.split(" (")
            self.subject = p[0].strip()
            self.teacher = p[1].replace(")", "").strip() if len(p) > 1 else "TBD"
        elif " / " in course_name:
            p = course_name.split(" / ")
            self.subject, self.teacher = p[0].strip(), (p[1].strip() if len(p) > 1 else "TBD")
        else:
            self.subject, self.teacher = course_name.strip(), "TBD"

    def _detect_course_type(self):
        u = self.course_name.upper()
        if "CM" in u:
            return "CM"
        if "TD" in u:
            return "TD"
        if "TP" in u:
            return "TP"
        if "EXAM" in u or "EXAMEN" in u:
            return "EXAM"
        return "OTHER"

    def _convert_time(self, time_slot):
        try:
            s = time_slot.lower().replace('h', ' ').replace(':', ' ')
            s = re.sub(r'[^\d\-]', '', s.replace(' ', ''))
            if '-' in s:
                a, b = s.split('-')[:2]
                start = int(re.match(r'\d{1,2}', a).group())
                end = int(re.match(r'\d{1,2}', b).group())
                return start, end
            return 0, 0
        except Exception:
            return 0, 0

    def set_priority(self, priority):
        self.priority = max(1, min(10, priority))

    def __str__(self):
        return f"{self.group} - {self.subject} - {self.day} {self.time_slot}"

    def to_dict(self):
        return {
            "id": self.id, "group": self.group, "main_group": self.main_group,
            "track": self.track, "day": self.day, "time_slot": self.time_slot,
            "subject": self.subject, "teacher": self.teacher, "students": self.students,
            "start": self.start, "end": self.end, "course_type": self.course_type,
            "priority": self.priority,
            "assigned_room": self.assigned_room.name if self.assigned_room else None,
            "assigned_room_capacity": self.assigned_room.capacity if self.assigned_room else None,
        }


# ============================================
# DATA LOADING
# ============================================
def _find_header_row(df):
    for idx in range(min(10, len(df))):
        for cell in df.iloc[idx].values:
            if isinstance(cell, str) and ('group' in cell.lower() or 'groupe' in cell.lower()):
                return idx
    return 0


COURSE_PRIORITY = {'CM': 10, 'TD': 8, 'TP': 7, 'EXAM': 9, 'OTHER': 5}


def parse_courses(path_or_buffer):
    """Read a courses-only file (EN or FR headers, NO room column) -> list of Course."""
    df = pd.read_excel(path_or_buffer, header=None)
    header_row = _find_header_row(df)
    courses = []
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        if len(row) < 4 or pd.isna(row[0]):
            continue
        group = str(row[0]).strip()
        if not group or group.lower() in ['group', 'groupe', 'day', 'jour', 'nan', '']:
            continue
        try:
            day = str(row[1]).strip() if pd.notna(row[1]) else ""
            time_slot = str(row[2]).strip() if pd.notna(row[2]) else ""
            course_name = str(row[3]).strip() if pd.notna(row[3]) else ""
            students = row[4] if (len(row) > 4 and pd.notna(row[4])) else 0
            if group and day and time_slot and course_name:
                c = Course(group, day, time_slot, course_name, students)
                c.set_priority(COURSE_PRIORITY.get(c.course_type, 5))
                courses.append(c)
        except Exception:
            continue
    return courses


# ============================================
# EVOLUTIONARY ALLOCATOR
# ============================================
# No virtual "buffer" rooms: the allocator works with the REAL room catalogue only
# (rooms_config.json). Set EXTRA_BUFFER_ROOMS > 0 only to re-enable the old behaviour.
EXTRA_BUFFER_ROOMS = 0
COURSES_PER_ROOM_OVERLOAD_RATIO = 5


class EvolutionaryAllocator:
    def __init__(self, courses, rooms, constraint_manager=None, params=None):
        # Ajout direct dans le code : si le parc de salles reelles est trop
        # petit face au nombre de cours (ex: 24 salles pour 1200 cours),
        # aucune combinaison sans conflit n'existe et le fitness retombe
        # systematiquement a 0 (max(0, 1000 - conflicts + bonus)). On ajoute
        # alors ici EXTRA_BUFFER_ROOMS (10) salles supplementaires pour que
        # l'algorithme puisse continuer a travailler et produire un fitness.
        if (EXTRA_BUFFER_ROOMS > 0 and rooms and courses
                and len(courses) > len(rooms) * COURSES_PER_ROOM_OVERLOAD_RATIO):
            rooms = list(rooms)
            for i in range(1, EXTRA_BUFFER_ROOMS + 1):
                buf = Room(DEFAULT_INSTITUTION_LOCATION, "Salle petite",
                           f"Salle tampon {i}", 30, room_id=f"buffer_{i}")
                buf.name = f"Salle tampon {i}"
                rooms.append(buf)

        self.courses = courses
        self.rooms = rooms
        self.constraint_manager = constraint_manager or ConstraintManager()
        self.nb_courses = len(courses)
        self.nb_rooms = len(rooms)
        self.occupations = {}

        p = params or {}
        self.population_size = p.get('population_size', DEFAULT_POPULATION_SIZE)
        self.number_generations = p.get('number_generations', DEFAULT_NUMBER_GENERATIONS)
        self.mutation_rate = p.get('mutation_rate', DEFAULT_MUTATION_RATE)
        self.tournament_size = p.get('tournament_size', DEFAULT_TOURNAMENT_SIZE)
        self.elitism_count = p.get('elitism_count', DEFAULT_ELITISM_COUNT)
        self.capacity_penalty = p.get('capacity_penalty', DEFAULT_CAPACITY_PENALTY)
        self.teacher_conflict_penalty = p.get('teacher_conflict_penalty', DEFAULT_TEACHER_CONFLICT_PENALTY)
        self.group_distribution_penalty = p.get('group_distribution_penalty', DEFAULT_GROUP_DISTRIBUTION_PENALTY)

        self._fitness_cache = {}

        self.best_fitness_history = []
        self.avg_fitness_history = []
        self.min_fitness_history = []
        self.conflicts_history = []
        # Statistical panel data: population fitness variance / standard
        # deviation recorded generation by generation (diversity /
        # convergence indicator of the fitness function across the run).
        self.variance_fitness_history = []
        self.stdev_fitness_history = []

    def _count_hard_conflicts(self, individual):
        occ = {}
        conflicts = 0
        for i, room_idx in enumerate(individual):
            c = self.courses[i]
            key = (room_idx, c.day)
            if key in occ:
                for (s, e) in occ[key]:
                    if not (c.end <= s or c.start >= e):
                        conflicts += 1
                occ[key].append((c.start, c.end))
            else:
                occ[key] = [(c.start, c.end)]
        return conflicts

    def _repair_capacity_overbookings(self, individual):
        """Etape de reparation locale executee apres convergence du GA :
        pour chaque cours encore en depassement de capacite dans la
        meilleure solution trouvee, cherche une salle suffisamment grande
        et libre sur le meme creneau/jour (sans creer de nouveau conflit
        d'occupation) et reaffecte le cours vers celle-ci. Necessaire car
        le GA seul peut rester bloque dans un optimum local ou 1-2
        depassements subsistent malgre une capacite globale suffisante
        (cf. tests : jusqu'a 600 generations sans amelioration sur certains
        seeds difficiles)."""
        individual = list(individual)

        occ = {}
        for i, room_idx in enumerate(individual):
            c = self.courses[i]
            occ.setdefault((room_idx, c.day), []).append((c.start, c.end, i))

        for i, room_idx in enumerate(individual):
            course = self.courses[i]
            room = self.rooms[room_idx]
            if course.students <= room.capacity:
                continue

            candidates = [(idx, r) for idx, r in enumerate(self.rooms)
                          if r.capacity >= course.students]
            candidates.sort(key=lambda x: x[1].capacity)  # plus petite salle suffisante d'abord

            for idx, cand_room in candidates:
                key = (idx, course.day)
                conflict = False
                for (s, e, j) in occ.get(key, []):
                    if j == i:
                        continue
                    if not (course.end <= s or course.start >= e):
                        conflict = True
                        break
                if conflict:
                    continue

                old_key = (room_idx, course.day)
                occ[old_key] = [t for t in occ.get(old_key, []) if t[2] != i]
                occ.setdefault(key, []).append((course.start, course.end, i))
                individual[i] = idx
                room_idx = idx
                break

        return individual

    def _repair_room_time_overlaps(self, individual):
        """Post-convergence repair for room/time-slot overlaps, mirroring
        _repair_capacity_overbookings above: for every session still in
        conflict with another session in the same room on the same day,
        try to move it to another room that is both suitable (capacity,
        teacher availability, required type) AND actually free at that
        exact day/time. Sessions are processed in a fixed order, and each
        successfully repaired session immediately frees its previous slot
        and occupies its new one, so later sessions in the loop see an
        up-to-date occupancy picture. Without this step, overlaps were
        only discouraged via the fitness-function penalty (weight 25) and
        could remain very numerous in the final solution whenever the
        room catalogue is small relative to the number of sessions."""
        individual = list(individual)

        occ = {}
        for i, room_idx in enumerate(individual):
            c = self.courses[i]
            occ.setdefault((room_idx, c.day), []).append((c.start, c.end, i))

        def _is_free(room_idx, day, start, end, skip_i):
            for (s, e, j) in occ.get((room_idx, day), []):
                if j == skip_i:
                    continue
                if not (end <= s or start >= e):
                    return False
            return True

        for i, room_idx in enumerate(individual):
            course = self.courses[i]
            if _is_free(room_idx, course.day, course.start, course.end, i):
                continue  # this session is not actually in conflict

            candidates = self._suitable_rooms(course)  # capacity/teacher/type OK, ascending by size
            new_idx = None
            for idx in candidates:
                if _is_free(idx, course.day, course.start, course.end, i):
                    new_idx = idx
                    break
            if new_idx is None:
                # No suitable+free room exists for this exact slot in the
                # whole catalogue: this session's overlap cannot be
                # resolved without also moving another session, which is
                # out of scope for this lightweight, single-pass repair.
                continue

            old_key = (room_idx, course.day)
            occ[old_key] = [t for t in occ.get(old_key, []) if t[2] != i]
            occ.setdefault((new_idx, course.day), []).append((course.start, course.end, i))
            individual[i] = new_idx

        return individual

    def _count_capacity_overbookings(self, individual):
        """Nombre de cours dont l'effectif depasse la capacite de la salle
        assignee dans cette solution. Utilise pour empecher l'arret anticipe
        de l'algorithme tant qu'un depassement de capacite subsiste, alors
        meme qu'une solution sans depassement est generalement atteignable
        (le parc de salles offre largement assez de capacite globale)."""
        n = 0
        for i, room_idx in enumerate(individual):
            c = self.courses[i]
            room = self.rooms[room_idx]
            if c.students > room.capacity:
                n += 1
        return n

    def evaluate_solution(self, individual):
        cache_key = tuple(individual)
        if cache_key in self._fitness_cache:
            return self._fitness_cache[cache_key]

        conflicts = 0.0
        bonus = 0.0
        occ = {}
        group_day = {}
        teacher_day = {}

        for i, room_idx in enumerate(individual):
            course = self.courses[i]
            room = self.rooms[room_idx]

            if room.capacity < course.students:
                conflicts += (course.students - room.capacity) * self.capacity_penalty
            if not self.constraint_manager.is_room_allowed_for_course(room, course):
                conflicts += 50
            if not self.constraint_manager.is_teacher_available(course.teacher, course.day, course.start, course.end):
                conflicts += self.teacher_conflict_penalty
            bonus += self.constraint_manager.get_room_preference_bonus(course, room)

            for feat in course.required_features:
                if not room.has_feature(feat):
                    conflicts += 10

            req = self.constraint_manager.get_required_room_type(course)
            if req and req not in room.type:
                conflicts += 30

            key = (room_idx, course.day)
            if key in occ:
                for (s, e) in occ[key]:
                    if not (course.end <= s or course.start >= e):
                        conflicts += 25
                occ[key].append((course.start, course.end))
            else:
                occ[key] = [(course.start, course.end)]

            group_day[(course.group, course.day)] = group_day.get((course.group, course.day), 0) + 1
            if is_known_teacher(course.teacher):
                teacher_day[(course.teacher, course.day)] = teacher_day.get((course.teacher, course.day), 0) + 1

        for (group, _), n in group_day.items():
            if group in self.constraint_manager.group_distribution:
                m = self.constraint_manager.group_distribution[group]
                if n > m:
                    conflicts += (n - m) * self.group_distribution_penalty
        for (_, _), n in teacher_day.items():
            if n > 4:
                conflicts += (n - 4) * 5

        for i, room_idx in enumerate(individual):
            course = self.courses[i]
            room = self.rooms[room_idx]
            if course.priority > 5:
                bonus += course.priority / 2
            if course.students and room.capacity > course.students * 3:
                conflicts += 5

        # Facteur "nombre de salles disponibles" : on ne rajoute JAMAIS de
        # salle virtuelle au catalogue (self.nb_rooms reste la verite du
        # parc reel, cf. get_salles()/load_or_init_rooms()). En revanche on
        # utilise ce nombre pour ponderer le bonus de diversite, afin que le
        # fitness varie selon la richesse reelle du parc de salles au lieu
        # de rester plat quel que soit self.nb_rooms :
        #   - avec beaucoup de salles dispo, etaler les cours sur plus de
        #     salles distinctes est recompense davantage (marge de choix
        #     reelle) ;
        #   - avec peu de salles, le meme etalement (relatif) rapporte un
        #     bonus plus modeste, ce qui reflete la contrainte reelle sans
        #     jamais inventer de salles supplementaires.
        distinct_rooms_used = len(set(individual))
        if self.nb_rooms > 0:
            room_availability_ratio = distinct_rooms_used / self.nb_rooms
        else:
            room_availability_ratio = 0.0
        bonus += distinct_rooms_used * 0.5
        bonus += room_availability_ratio * 15.0

        base_score = 100.0 * max(1, self.nb_courses)
        score = max(0.0, base_score - conflicts + bonus)
        self._fitness_cache[cache_key] = score
        return score

    def _suitable_rooms(self, course):
        """Rooms that satisfy capacity, teacher-availability and required
        room-type for this course, sorted by capacity ascending (smallest
        adequate room first) so that callers can bias their choice toward
        a tight fit instead of drawing uniformly among rooms of very
        different sizes (which is what was causing many sessions to land
        in large amphitheatres regardless of their real headcount)."""
        out = []
        for idx, room in enumerate(self.rooms):
            if room.capacity >= course.students and self.constraint_manager.is_teacher_available(
                    course.teacher, course.day, course.start, course.end):
                req = self.constraint_manager.get_required_room_type(course)
                if req and req not in room.type:
                    continue
                out.append(idx)
        out.sort(key=lambda idx: self.rooms[idx].capacity)
        return out

    def _pick_room_biased(self, candidate_idxs):
        """Picks a room among already-sorted (ascending capacity) candidate
        indices, favouring a tight fit: 70% of the time restrict the draw
        to the smallest few candidates (reduces gross over-capacity),
        30% of the time draw uniformly among all candidates (keeps enough
        randomness for crossover/mutation to explore and for the
        room-diversity bonus to still matter)."""
        if not candidate_idxs:
            return None
        if random.random() < 0.7:
            k = min(3, len(candidate_idxs))
            return random.choice(candidate_idxs[:k])
        return random.choice(candidate_idxs)

    @staticmethod
    def _overlaps_existing(intervals, start, end):
        return any(not (end <= s or start >= e) for (s, e) in intervals)

    def create_individual(self):
        """Builds one chromosome greedily but stochastically: courses are
        assigned one after another, tracking which (room, day) slots are
        already occupied by earlier picks in THIS individual, so that a
        suitable AND currently-free room is preferred whenever one exists.
        This does not guarantee a conflict-free schedule on its own (the
        room catalogue may simply be too small for the instance), but it
        gives the evolutionary search a much better starting population
        than picking rooms independently at random per course, which
        ignored occupancy entirely and produced very high room-time
        overlap counts."""
        ind = []
        occ = {}
        for course in self.courses:
            suit = self._suitable_rooms(course)
            free_suit = [idx for idx in suit
                         if not self._overlaps_existing(occ.get((idx, course.day), []), course.start, course.end)]
            if free_suit:
                choice = self._pick_room_biased(free_suit)
            elif suit:
                # No suitable room is free at this exact slot: fall back to
                # a suitable room anyway (best effort) rather than an
                # arbitrary one, biased toward a tight fit.
                choice = self._pick_room_biased(suit)
            else:
                choice = random.randint(0, self.nb_rooms - 1)
            ind.append(choice)
            occ.setdefault((choice, course.day), []).append((course.start, course.end))
        return ind

    def tournament_selection(self, population, fitnesses):
        best, best_fit = None, -1
        for _ in range(self.tournament_size):
            idx = random.randint(0, len(population) - 1)
            if fitnesses[idx] > best_fit:
                best_fit, best = fitnesses[idx], population[idx].copy()
        return best

    def crossover(self, p1, p2):
        if self.nb_courses <= 2:
            return p1.copy(), p2.copy()
        num_points = min(random.randint(1, 3), self.nb_courses - 2)
        points = sorted(random.sample(range(1, self.nb_courses - 1), num_points))
        c1, c2 = p1.copy(), p2.copy()
        for i in range(len(points)):
            start = points[i] if i == 0 else points[i - 1] + 1
            end = points[i + 1] if i < len(points) - 1 else self.nb_courses
            if i % 2 == 0:
                c1[start:end], c2[start:end] = p2[start:end], p1[start:end]
        return c1, c2

    def mutate(self, individual):
        for i in range(len(individual)):
            if random.random() < self.mutation_rate:
                suit = self._suitable_rooms(self.courses[i])
                if suit and random.random() < 0.7:
                    individual[i] = self._pick_room_biased(suit)
                else:
                    individual[i] = random.randint(0, self.nb_rooms - 1)
        return individual

    def allocate(self, callback=None, stop_flag=None):
        self._fitness_cache = {}
        population = [self.create_individual() for _ in range(self.population_size)]
        best_history, avg_history, min_history, conf_history = [], [], [], []
        best_individual, best_fitness = None, -1
        no_improve = 0

        for gen in range(self.number_generations):
            if stop_flag and stop_flag():
                break

            fitnesses = [self.evaluate_solution(ind) for ind in population]
            g_best = max(fitnesses)
            g_avg = sum(fitnesses) / len(fitnesses)
            g_min = min(fitnesses)
            best_idx = fitnesses.index(g_best)
            # Population-level dispersion of the fitness function for this
            # generation (statistical panel: variance / standard deviation).
            g_var = statistics.pvariance(fitnesses) if len(fitnesses) > 1 else 0.0
            g_std = statistics.pstdev(fitnesses) if len(fitnesses) > 1 else 0.0

            best_history.append(g_best)
            avg_history.append(g_avg)
            min_history.append(g_min)
            conf_history.append(self._count_hard_conflicts(population[best_idx]))
            self.variance_fitness_history.append(g_var)
            self.stdev_fitness_history.append(g_std)

            if g_best > best_fitness:
                best_fitness = g_best
                best_individual = population[best_idx].copy()
                no_improve = 0
            else:
                no_improve += 1

            if callback:
                callback(gen, g_best, g_avg)

            if no_improve > self.number_generations * 0.3 and gen > self.number_generations * 0.5:
                # On ne s'arrete jamais prematurement s'il reste un
                # depassement de capacite dans la meilleure solution
                # trouvee jusqu'ici : on laisse l'algorithme continuer
                # jusqu'a la fin des generations pour tenter de l'eliminer,
                # puisque le parc de salles a globalement assez de capacite.
                if best_individual is None or self._count_capacity_overbookings(best_individual) == 0:
                    break

            ranked = sorted(zip(population, fitnesses), key=lambda x: x[1], reverse=True)
            new_pop = [ind.copy() for ind, _ in ranked[:self.elitism_count]]
            while len(new_pop) < self.population_size:
                p1 = self.tournament_selection(population, fitnesses)
                p2 = self.tournament_selection(population, fitnesses)
                c1, c2 = self.crossover(p1, p2)
                new_pop.append(self.mutate(c1))
                if len(new_pop) < self.population_size:
                    new_pop.append(self.mutate(c2))
            population = new_pop
            self._fitness_cache = {}

        self._fitness_cache = {}
        if best_individual is None:
            fitnesses = [self.evaluate_solution(ind) for ind in population]
            best_individual = population[fitnesses.index(max(fitnesses))].copy()

        if self._count_capacity_overbookings(best_individual) > 0:
            best_individual = self._repair_capacity_overbookings(best_individual)

        if self._count_hard_conflicts(best_individual) > 0:
            best_individual = self._repair_room_time_overlaps(best_individual)
            # The overlap repair only moves sessions into rooms that already
            # satisfy capacity, so it should not (re)introduce capacity
            # overbookings — but check once more anyway, defensively.
            if self._count_capacity_overbookings(best_individual) > 0:
                best_individual = self._repair_capacity_overbookings(best_individual)

        self.occupations = {}
        results = []
        for i, room_idx in enumerate(best_individual):
            course = self.courses[i]
            room = self.rooms[room_idx]
            course.assigned_room = room
            course.assigned_room_id = room.id
            self.occupations.setdefault((room.name, course.day), []).append((course.start, course.end))
            results.append({'course': course, 'room': room})

        self.best_fitness_history = best_history
        self.avg_fitness_history = avg_history
        self.min_fitness_history = min_history
        self.conflicts_history = conf_history
        return results, [], best_history, avg_history

    def verify_constraints(self, results):
        """Actually checks, on the final allocation result (a list of
        {'course', 'room'}), whether each hard/soft constraint is
        satisfied. Unlike a static description, every entry returned here
        carries the number of violations really detected on this specific
        solution and a satisfied=True/False status (or None when the
        constraint is a pure bonus with no violation concept, e.g. room
        diversity)."""

        # ---------------- HARD ----------------
        hard = []

        cap_violations = sum(
            1 for r in results if r['course'].students > r['room'].capacity)
        hard.append({
            "key": "capacity", "name": "Room capacity",
            "detail": "The number of students must not exceed the capacity of the assigned room.",
            "violations": cap_violations, "satisfied": cap_violations == 0,
        })

        occ = {}
        overlap_violations = 0
        for r in results:
            c, room = r['course'], r['room']
            key = (room.name, c.day)
            for (s, e) in occ.get(key, []):
                if not (c.end <= s or c.start >= e):
                    overlap_violations += 1
            occ.setdefault(key, []).append((c.start, c.end))
        hard.append({
            "key": "overlap", "name": "Room/time-slot overlap",
            "detail": "Two sessions must not occupy the same room on the same day with overlapping times.",
            "violations": overlap_violations, "satisfied": overlap_violations == 0,
        })

        disallowed_violations = sum(
            1 for r in results
            if not self.constraint_manager.is_room_allowed_for_course(r['room'], r['course']))
        hard.append({
            "key": "disallowed_room", "name": "Disallowed room",
            "detail": "The session must not be placed in a room explicitly excluded for it.",
            "violations": disallowed_violations, "satisfied": disallowed_violations == 0,
        })

        teacher_violations = sum(
            1 for r in results
            if is_known_teacher(r['course'].teacher) and not self.constraint_manager.is_teacher_available(
                r['course'].teacher, r['course'].day, r['course'].start, r['course'].end))
        hard.append({
            "key": "teacher_availability", "name": "Teacher availability",
            "detail": "The teacher must not have a session scheduled during a declared unavailability. "
                      "Sessions with no professor specified in the source data are not counted here.",
            "violations": teacher_violations, "satisfied": teacher_violations == 0,
        })

        type_violations = 0
        for r in results:
            req = self.constraint_manager.get_required_room_type(r['course'])
            if req and req not in r['room'].type:
                type_violations += 1
        hard.append({
            "key": "room_type", "name": "Required room type",
            "detail": "Some session types require a specific room type (e.g. TP -> specialised room).",
            "violations": type_violations, "satisfied": type_violations == 0,
        })

        # ---------------- SOFT ----------------
        soft = []

        missing_feature_violations = 0
        for r in results:
            for feat in r['course'].required_features:
                if not r['room'].has_feature(feat):
                    missing_feature_violations += 1
        soft.append({
            "key": "features", "name": "Requested equipment/feature",
            "detail": "Equipment requested by the session should be available in the assigned room.",
            "violations": missing_feature_violations, "satisfied": missing_feature_violations == 0,
        })

        preferred_used = sum(
            1 for r in results
            if self.constraint_manager.get_room_preference_bonus(r['course'], r['room']) > 0)
        soft.append({
            "key": "preferred_room", "name": "Preferred room",
            "detail": "Bonus when a session is placed in one of its preferred rooms.",
            "violations": None, "satisfied": None,
            "info": f"{preferred_used}/{len(results)} session(s) in a preferred room",
        })

        high_priority = sum(1 for r in results if r['course'].priority > 5)
        soft.append({
            "key": "priority", "name": "Session priority",
            "detail": "Bonus for high-priority sessions (lectures, exams...).",
            "violations": None, "satisfied": None,
            "info": f"{high_priority}/{len(results)} high-priority session(s)",
        })

        distinct_rooms = len(set(r['room'].name for r in results))
        soft.append({
            "key": "diversity", "name": "Room-catalogue diversity",
            "detail": "Bonus for using a larger share of the available room catalogue.",
            "violations": None, "satisfied": None,
            "info": f"{distinct_rooms}/{self.nb_rooms} distinct room(s) used",
        })

        group_day = {}
        for r in results:
            c = r['course']
            group_day[(c.group, c.day)] = group_day.get((c.group, c.day), 0) + 1
        group_overload = 0
        for (group, _), n in group_day.items():
            if group in self.constraint_manager.group_distribution:
                m = self.constraint_manager.group_distribution[group]
                if n > m:
                    group_overload += (n - m)
        soft.append({
            "key": "group_daily_load", "name": "Daily load per group",
            "detail": "Preferred maximum number of sessions per day for a given group.",
            "violations": group_overload, "satisfied": group_overload == 0,
        })

        teacher_day = {}
        for r in results:
            c = r['course']
            if is_known_teacher(c.teacher):
                teacher_day[(c.teacher, c.day)] = teacher_day.get((c.teacher, c.day), 0) + 1
        teacher_overload = sum(max(0, n - 4) for n in teacher_day.values())
        soft.append({
            "key": "teacher_daily_load", "name": "Daily load per teacher",
            "detail": "A teacher scheduled beyond 4 sessions/day is penalised. Sessions with no "
                      "professor specified in the source data are not counted here.",
            "violations": teacher_overload, "satisfied": teacher_overload == 0,
        })

        gross_overcapacity = sum(
            1 for r in results
            if r['course'].students and r['room'].capacity > r['course'].students * 3)
        soft.append({
            "key": "gross_overcapacity", "name": "Excessive over-capacity",
            "detail": "Light penalty when a room is far larger than the session's headcount needs.",
            "violations": gross_overcapacity, "satisfied": gross_overcapacity == 0,
        })

        return {"hard": hard, "soft": soft}


def configure_scenario(n_courses):
    """Suggest GA parameters based on the size of the timetable (mirrors the desktop tool)."""
    if n_courses <= 20:
        label = f"Departement ({n_courses} cours)"
        pop, gen = 80, 150
    elif n_courses <= 80:
        label = f"Faculte ({n_courses} cours)"
        pop, gen = 200, 500
    else:
        label = f"Grande echelle ({n_courses} cours)"
        pop, gen = 300, 1000
    return label, pop, gen