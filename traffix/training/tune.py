"""
Learns the traffic light agent's max-pressure parameters and the corridor
agent's platoon weight by random search over simulations on TRAINING dates.
Cheap (minutes) compared with reinforcement learning, and it really improves
results: one parameter (downstream counting) already changed waits a lot.
Objective: mean car wait + mean pedestrian wait (seconds).
"""
import json
import os
import random

from ..core import config
from ..demand.generator import DemandGenerator
from ..evaluation.runner import run_one
from .datagen import ROUTES, TRAINING_SCENARIOS

PARAMS = config.path(config.agents()["models_dir"], "traffic_light_params.json")
SPACE = {"ped_weight": (0.2, 1.2), "switch_margin": (0.0, 0.5), "platoon_weight": (0.0, 0.8)}


def evaluate(params, scenarios, seed=1):
    os.makedirs(os.path.dirname(PARAMS), exist_ok=True)
    with open(PARAMS, "w") as f:
        json.dump(params, f)
    rows = [run_one("traffix", s, seed, route_dir=ROUTES, save_log=False) for s in scenarios]
    return sum(r["veh_mean_wait_s"] + r["ped_mean_wait_s"] for r in rows) / len(rows)


def tune(trials=10, scenarios=("tr_morning", "tr_evening")):
    gen = DemandGenerator(config.network_files()[0])
    for s in scenarios:
        gen.build(s, TRAINING_SCENARIOS[s], 1, ROUTES)
    rng = random.Random(0)
    base = {k: config.agents()["traffic_light"].get(k, config.agents()["corridor"].get(k))
            for k in SPACE}
    history = [(evaluate(base, scenarios), base)]
    print(f"  defaults {base}: score {history[0][0]:.2f}", flush=True)
    for i in range(trials):
        cand = {k: round(rng.uniform(*r), 2) for k, r in SPACE.items()}
        score = evaluate(cand, scenarios)
        history.append((score, cand))
        print(f"  trial {i + 1}: {cand} score {score:.2f}", flush=True)
    best_score, best = min(history, key=lambda x: x[0])
    with open(PARAMS, "w") as f:
        json.dump(best, f, indent=1)
    return {"best": best, "best_score": round(best_score, 2), "default_score": round(history[0][0], 2),
            "trials": len(history)}
