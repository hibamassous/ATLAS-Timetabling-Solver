# -*- coding: utf-8 -*-
"""
Runs the room-allocation genetic algorithm 30 independent times on the
dataset (200_EDT_v1.xlsx, 1200 course sessions) against the room catalogue
stored in rooms_config.json, and reports timing and quality statistics across
the 30 runs. Progress is written to progress.json after every run so it can
be polled without blocking.

Usage:  python run_30_experiments.py [courses.xlsx]
"""

import json
import random
import statistics
import sys
import time

sys.path.insert(0, ".")
import allocator as core
import engine

N_RUNS = 30
GA_PARAMS = {
    "population_size": 60,
    "number_generations": 300,
    "mutation_rate": 0.05,
}
CROSSOVER_RATE = 0.8

DATASET_FILE = sys.argv[1] if len(sys.argv) > 1 else "200_EDT_v1.xlsx"
PROGRESS_FILE = "progress.json"
RESULTS_FILE = "results_30_runs.json"


def write_progress(done, total, elapsed_total, last_run=None):
    payload = {
        "done": done,
        "total": total,
        "elapsed_total_seconds": round(elapsed_total, 1),
        "last_run": last_run,
    }
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def run_once(course_objs, rooms, seed):
    random.seed(seed)
    ga = core.EvolutionaryAllocator(course_objs, rooms, params=GA_PARAMS)

    base_crossover = ga.crossover

    def _crossover(p1, p2):
        if random.random() > CROSSOVER_RATE:
            return p1.copy(), p2.copy()
        return base_crossover(p1, p2)

    ga.crossover = _crossover

    t0 = time.time()
    results, _, best_hist, avg_hist = ga.allocate()
    t1 = time.time()

    n_over = sum(1 for r in results if r["course"].students > r["room"].capacity)
    rooms_used = sorted(set(r["room"].name for r in results))

    return {
        "seed": seed,
        "final_fitness": round(best_hist[-1], 1) if best_hist else 0,
        "allocated": len(results),
        "total_courses": len(course_objs),
        "capacity_overbookings": n_over,
        "rooms_used": len(rooms_used),
        "rooms_total": len(rooms),
        "generations_run": len(best_hist),
        "execution_time_seconds": round(t1 - t0, 3),
    }


def main():
    print(f"Loading course dataset ({DATASET_FILE})...")
    cours, warnings = engine.charger_cours(DATASET_FILE)
    print(f"Loaded {len(cours)} course sessions ({len(warnings)} warnings).")

    course_objs = []
    for c in cours:
        co = core.Course(
            c["num_edt"], c["jour"], f'{c["debut"]}h-{c["fin"]}h',
            f'{c["module"]} - {c["prof"]}', c["effectif"])
        co.set_priority(c.get("_priority", 5))
        course_objs.append(co)

    rooms = core.load_or_init_rooms()
    print(f"Room catalogue: {len(rooms)} rooms.")
    print(f"GA parameters: population={GA_PARAMS['population_size']}, "
          f"generations={GA_PARAMS['number_generations']}, "
          f"crossover_rate={CROSSOVER_RATE}, mutation_rate={GA_PARAMS['mutation_rate']}")
    print(f"Running {N_RUNS} independent runs (different random seed each time)...")

    all_results = []
    total_start = time.time()
    write_progress(0, N_RUNS, 0.0)

    for i in range(1, N_RUNS + 1):
        run_result = run_once(course_objs, rooms, seed=1000 + i)
        run_result["run_id"] = i
        all_results.append(run_result)
        elapsed_total = time.time() - total_start
        print(f"Run {i}/{N_RUNS}: fitness={run_result['final_fitness']}, "
              f"overbookings={run_result['capacity_overbookings']}, "
              f"time={run_result['execution_time_seconds']}s, "
              f"total_elapsed={elapsed_total:.1f}s", flush=True)
        write_progress(i, N_RUNS, elapsed_total, last_run=run_result)
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)

    total_elapsed = time.time() - total_start

    # ---- Aggregate statistics ----
    def agg(key):
        vals = [r[key] for r in all_results]
        return {
            "mean": round(statistics.mean(vals), 3),
            "stdev": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0,
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
            "median": round(statistics.median(vals), 3),
        }

    summary = {
        "n_runs": N_RUNS,
        "n_courses": len(course_objs),
        "n_rooms": len(rooms),
        "ga_parameters": {**GA_PARAMS, "crossover_rate": CROSSOVER_RATE},
        "total_wall_clock_seconds": round(total_elapsed, 1),
        "final_fitness": agg("final_fitness"),
        "capacity_overbookings": agg("capacity_overbookings"),
        "execution_time_seconds": agg("execution_time_seconds"),
        "generations_run": agg("generations_run"),
        "rooms_used": agg("rooms_used"),
    }

    with open("summary_30_runs.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n=== DONE ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()