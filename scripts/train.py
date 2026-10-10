"""
The whole training pipeline (about 15-30 minutes on a laptop):

  python scripts/train.py              generate data, train models, tune traffic lights
  python scripts/train.py --skip-data  reuse data/training/*.csv
  python scripts/train.py --skip-tune  models only
"""
import argparse
import json

import _path  # noqa: F401
from traffix.training import datagen, train_models, tune

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--skip-data", action="store_true")
    p.add_argument("--skip-tune", action="store_true")
    p.add_argument("--trials", type=int, default=8)
    a = p.parse_args()
    if not a.skip_data:
        print("1/3 Generating training data (2025 dates)...")
        print(datagen.generate())
    print("2/3 Training models...")
    print(json.dumps(train_models.train_all(), indent=1))
    if not a.skip_tune:
        print("3/3 Tuning traffic light and corridor parameters...")
        print(tune.tune(a.trials))
    print("Models saved in models/")
