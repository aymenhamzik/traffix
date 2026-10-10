"""
Runs controllers x scenarios x seeds and saves results/results.csv.

  python scripts/run_experiments.py
  python scripts/run_experiments.py --scenario emergency --controller traffix --seeds 1
  python scripts/run_experiments.py --gui --scenario rain --controller traffix --seeds 1
"""
import argparse
import csv
import os
from multiprocessing import Pool

import _path  # noqa: F401
from traffix.core import config


def job(args):
    from traffix.evaluation.runner import run_one
    return run_one(*args)


if __name__ == "__main__":
    sim, sc = config.simulation(), config.scenarios()
    p = argparse.ArgumentParser()
    p.add_argument("--controller", nargs="+", default=sim["controllers"], choices=sim["controllers"])
    p.add_argument("--scenario", nargs="+", default=list(sc), choices=list(sc))
    p.add_argument("--seeds", nargs="+", type=int, default=sim["seeds"])
    p.add_argument("--workers", type=int, default=sim["workers"])
    p.add_argument("--gui", action="store_true")
    p.add_argument("--out", default=config.path("results", "results.csv"))
    a = p.parse_args()
    jobs = [(c, s, seed, a.gui) for s in a.scenario for c in a.controller for seed in a.seeds]
    print(f"Running {len(jobs)} simulations")
    rows = []
    if a.gui or a.workers <= 1:
        results = map(job, jobs)
    else:
        results = Pool(a.workers).imap(job, jobs)
    for r in results:
        rows.append(r)
        print(f"{r['scenario']:18s} {r['controller']:14s} seed {r['seed']}: car wait "
              f"{r['veh_mean_wait_s']:6.1f}s  ped wait {r['ped_mean_wait_s']:6.1f}s  "
              f"unfinished {r['veh_unfinished']:3d}  truncations {r['clearance_truncations']:4d}", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print("Saved", a.out)
