# Coding Guidelines

**Last updated:** 2026-05-05 | **Python:** 3.12+ | **Pandas:** 2.2 | **Polars:** 1.40

## Overview
Python style and structure standards for ML project code. Lightweight and
pragmatic: tuned for a small ML project (single developer, no heavy MLOps
stack). Optimise for clarity, reproducibility, and debuggability — not for
infrastructure.

---

## 1. Python 3.12+ Modern Features

### Use New Type Syntax (PEP 695)
```python
# Modern (Python 3.12+)
def train_model[T](
    X: np.ndarray,
    y: np.ndarray,
    params: dict[str, T],
) -> lgb.Booster:
    ...

# Type aliases with the `type` statement
type Features = np.ndarray
type Target = np.ndarray

# Old style (avoid)
from typing import TypeVar
T = TypeVar("T")
```

### Built-in Generics (PEP 585) and `X | Y` Unions (PEP 604)
```python
features: list[str] = ["Stint", "TyreLife"]
scores: dict[str, float] = {"cv": 0.9496}
params: dict[str, int | float] = {"num_leaves": 64, "lr": 0.03}

def load_data(path: str | Path) -> pd.DataFrame:
    ...

# Avoid the legacy capital-T forms
from typing import List, Dict, Union  # don't import these for typing
```

### `typing.override` (PEP 698)
```python
from typing import override

class BaseModel:
    def predict(self, X: np.ndarray) -> np.ndarray:
        ...

class LGBMModel(BaseModel):
    @override  # type checker errors if BaseModel.predict is renamed/removed
    def predict(self, X: np.ndarray) -> np.ndarray:
        ...
```

### Structural Pattern Matching (PEP 634, 3.10+)
Useful for clean dispatch in feature engineering / model selection:
```python
def get_trainer(name: str):
    match name:
        case "lgbm":
            return train_lgbm
        case "xgb":
            return train_xgb
        case _:
            raise ValueError(f"Unknown model: {name}")
```

### `tomllib` for Config (stdlib since 3.11)
No external dep needed to read TOML config files:
```python
import tomllib

with open("config.toml", "rb") as f:
    cfg = tomllib.load(f)
```

### Lazy Imports for Type-Only Dependencies
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sklearn.model_selection import StratifiedKFold
```

---

## 2. Pandas vs Polars: When to Use Which

### Performance Benchmarks (2026)

| Operation | Dataset Size | Pandas 2.2 | Polars 1.40 | Speedup |
|-----------|-------------|------------|-------------|---------|
| CSV Read | 3M rows | 8.42s | 1.61s | **5.2×** |
| Parquet Read | 3M rows | 0.98s | 0.31s | **3.2×** |
| GroupBy + Agg | 3M rows | 142.6ms | 18.3ms | **7.8×** |
| Sort | 3M rows | 1,246ms | 108ms | **11.5×** |
| Left Join | 3M rows | 312ms | 46ms | **6.8×** |
| Full ETL Pipeline | 3M rows | 1,620ms | 98ms | **16.5×** |
| GroupBy 100M rows | 100M rows | 15–60s | 1–5s | **5–30×** |

**Rules of thumb:**
- **< 100K rows:** Pandas often matches or beats Polars (thread overhead).
- **100K – 1M rows:** Polars typically 2–5× faster.
- **> 1M rows:** Polars dominates (5–30× faster).
- **> RAM size:** Polars streaming works; Pandas crashes.

### When to Use Polars
1. **Large datasets** (>1M rows, >1GB) — ETL on full training sets, log analysis.
2. **Performance-critical bottlenecks** — group-by/aggregate, complex joins, sorts.
3. **Memory-constrained environments** — streaming engine (lock-free, spills to
   disk) processes >RAM datasets.
4. **Production ETL pipelines** — 3–10× end-to-end speedups.
5. **Greenfield projects** — best performance from day one.

### When to Use Pandas
1. **Small/medium datasets** (<100K rows) — notebooks, quick prototyping.
2. **ML model training & evaluation** — scikit-learn / LightGBM / XGBoost
   expect Pandas/NumPy natively.
3. **Heavy string manipulation** — Pandas 2.2 + PyArrow backend is ~10–20%
   faster than Polars on complex regex.
4. **Rich plotting ecosystem** — seaborn / matplotlib / plotly integration.
5. **Index-based operations** — `.loc`/`.iloc`, `PeriodIndex`, label alignment.

### Polars Caveats (still true in 2026)
- No native `Period` dtype, no multi-index, no `.loc`/`.iloc`.
- ML libraries usually expect Pandas/NumPy → `.to_pandas()` at the boundary.
- `null` vs `NaN` handling is stricter than Pandas.
- GroupBy doesn't sort by default; column order isn't preserved after joins.

### Hybrid Approach (Recommended)
```python
import polars as pl
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# Heavy ETL with Polars (streaming engine, never blows RAM)
train_df = (
    pl.scan_parquet("data/train.parquet")
    .filter(pl.col("year") >= 2022)
    .group_by("driver_id")
    .agg([
        pl.col("pit_next_lap").mean().alias("pit_rate"),
        pl.col("laptime").std().alias("laptime_std"),
    ])
    .collect(engine="streaming")
)

# Hand off to Pandas for ML
X_train = train_df.to_pandas()  # zero-copy when Arrow-backed
y_train = X_train.pop("pit_next_lap")

model = RandomForestClassifier()
model.fit(X_train, y_train)
```

---

## 3. Pandas Best Practices (2026)

### Performance-Critical Patterns
```python
import pandas as pd
import numpy as np

# Specify dtypes upfront — large speedup on big CSVs
df = pd.read_csv(
    "train.csv",
    dtype={
        "Driver": "category",
        "Compound": "category",
        "Race": "category",
        "Year": "int16",
    },
    usecols=["Driver", "Compound", "Race", "Year", "PitNextLap"],
)

# Categorical for low-cardinality strings
df["Driver"] = df["Driver"].astype("category")

# Downcast numeric types
df["TyreLife"] = pd.to_numeric(df["TyreLife"], downcast="integer")
df["LapTime (s)"] = pd.to_numeric(df["LapTime (s)"], downcast="float")

# Vectorised — never loop
df["LapTime_per_TyreLife"] = df["LapTime (s)"] / (df["TyreLife"] + 1e-3)

# Avoid: 10–100× slower
for idx, row in df.iterrows():
    df.loc[idx, "new_col"] = row["a"] * row["b"]

# Avoid: .apply() with Python lambda
df["new_col"] = df["col"].apply(lambda x: x * 2)  # slow

# Use built-in vectorised ops
df["new_col"] = df["col"] * 2
```

### Memory Optimisation
```python
def optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce memory by downcasting numeric and converting low-cardinality strings."""
    df = df.copy()  # don't mutate caller's frame
    for col in df.select_dtypes(include=["int"]).columns:
        df[col] = pd.to_numeric(df[col], downcast="integer")
    for col in df.select_dtypes(include=["float"]).columns:
        df[col] = pd.to_numeric(df[col], downcast="float")
    for col in df.select_dtypes(include=["object"]).columns:
        if df[col].nunique() / len(df) < 0.5:  # low cardinality
            df[col] = df[col].astype("category")
    return df

# Inspect after loading
df.info(memory_usage="deep")
```

### Method Chaining (Readable & Safe)
```python
# Clean chain — easy to read and step through in a debugger
features = (
    df.copy()
    .assign(
        TyreLife_sq=lambda x: x["TyreLife"] ** 2,
        LapTime_ratio=lambda x: x["LapTime (s)"] / x["TyreLife"],
    )
    .astype({"Stint": "int16"})
)

# Avoid one-liner chains spanning many transforms — hard to debug
features = df.copy().assign(...).astype(...).query(...).reset_index()
```

---

## 4. Polars Best Practices (2026)

### New Streaming Engine (Polars 1.30+)
The new streaming engine is lock-free, spills to disk, and is the recommended
path for anything that may approach RAM size. It will become the default in a
future release.
```python
import polars as pl

# Opt into the new streaming engine globally
pl.Config.set_engine_affinity("streaming")

# Or per-query: collect(engine="streaming")
df = (
    pl.scan_parquet("data/large_file.parquet")
    .filter(pl.col("year") >= 2022)
    .with_columns(
        (pl.col("laptime") / pl.col("tyrelife")).alias("laptime_ratio"),
    )
    .group_by("driver_id")
    .agg([
        pl.col("pit_next_lap").mean(),
        pl.col("laptime_ratio").std(),
    ])
    .collect(engine="streaming")
)
```

### Sink Directly to Disk (No Materialisation)
For ETL outputs that don't need to live in memory:
```python
(
    pl.scan_parquet("data/huge.parquet")
    .filter(pl.col("value") > 0)
    .group_by("category")
    .agg(pl.col("value").sum())
    .sink_parquet("out.parquet")  # also: sink_csv, sink_ipc
)
```

### Eager API for Small Data
```python
df = (
    pl.read_csv("small_file.csv")
    .filter(pl.col("value") > 0)
    .select(["id", "value"])
)
```

### Expression API (Optimised, Parallel)
```python
df = df.with_columns([
    (pl.col("a") * pl.col("b")).alias("product"),
    pl.col("category").str.to_uppercase(),
])

# Avoid Python lambdas — bypasses query optimisation
df = df.with_columns(
    pl.col("a").map_elements(lambda x: x * 2)  # slower
)
```

### Conversion to Pandas at ML Boundaries
```python
pl_df = pl.read_parquet("features.parquet")
pd_df = pl_df.to_pandas()  # zero-copy when Arrow-backed

model.fit(pd_df.drop("target", axis=1), pd_df["target"])
```

---

## 5. Formatting & Style

### Line Length and Indentation
- **Indentation:** 4 spaces, no tabs.
- **Line length:** **100 characters** (matches the project's Ruff config).
  - 79 (PEP 8 original) is impractical with type hints; 88 is Black's default.
  - Docstrings/comments: aim for ≤ 88 for readability.
- **Blank lines:** 2 before top-level functions/classes, 1 before methods.
- **Whitespace:** spaces around binary operators (`a = b + c`).

### Imports
```python
# Standard library
import os
import sys
from pathlib import Path

# Third party
import numpy as np
import pandas as pd
import polars as pl
import lightgbm as lgb
from sklearn.model_selection import StratifiedKFold

# Local
from utils import helper_func
```
- Group: stdlib → third-party → local, blank line between groups.
- One import per line, alphabetical within groups.
- No `from module import *`.
- Ruff (`I` rules) handles ordering and grouping automatically.

---

## 6. Documentation

### File-Level Docstring (Required)
Every `.py` file starts with a concise docstring:
```python
"""
Train LightGBM model with Optuna hyperparameter optimisation.

Performs Bayesian search over key LGBM parameters using 5-fold
group CV (grouped by race), then trains the final model on the full
training data. Outputs: submission CSV, feature importance, best params.
"""
```
Include: one-sentence purpose, key functionality, important outputs.

### Function Docstrings (Google Style)
```python
def make_features(
    df: pd.DataFrame,
    train_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Generate engineered features for pit-stop prediction.

    Adds frequency encoding, target encoding, interaction terms, and
    derived features (tyre life ratios, degradation rates, position
    indicators). Uses training-data statistics for consistent encoding
    across train/test splits.

    Args:
        df: DataFrame to transform (train or test).
        train_df: Training data for fitting encoders. If None, uses
            fallback values (e.g. test-time inference).

    Returns:
        DataFrame with original columns plus engineered features.

    Raises:
        KeyError: If required columns (Driver, Compound, Race) are
            missing from df.
    """
```

**Sections:** Description → Args → Returns → Raises (only if non-obvious).
**Length:** 2–5 sentences for simple functions, up to ~10 for complex ones.

### Inline Comments
```python
# Use harmonic mean for rate calculation (not arithmetic)
rate = 2 * (p * r) / (p + r)

# Clip outliers at the 99th percentile to prevent skew
values = np.clip(values, 0, np.percentile(values, 99))
```
Explain **why**, not **what**. Avoid redundant comments like
`x += 1  # increment x`.

---

## 7. Function Design

### Single Purpose
```python
# Bad: does too much
def process_data(df):
    # cleans, encodes, engineers, validates
    ...

# Good: one job each
def clean_data(df: pd.DataFrame) -> pd.DataFrame: ...
def encode_categorical(df: pd.DataFrame, encoders: dict) -> pd.DataFrame: ...
def engineer_features(df: pd.DataFrame) -> pd.DataFrame: ...
```

**Guidelines**
- **< 50 lines** ideal, **< 100** acceptable.
- **One responsibility** per function.
- **< 4 parameters** ideal — bundle more into a dataclass or dict.
- Avoid hidden side effects (don't mutate inputs unless documented).

### Reusable & Testable
```python
# Bad: hard-coded path, no return value
def load_and_train():
    df = pd.read_csv("/hardcoded/path/train.csv")
    ...

# Good: parameterised, returns artefacts
def train_model(
    X: np.ndarray,
    y: np.ndarray,
    params: dict[str, int | float],
    cv_folds: int = 5,
) -> tuple[lgb.Booster, list[float]]:
    """Train model with cross-validation."""
    ...
    return model, cv_scores
```

---

## 8. Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Variables | `snake_case` | `learning_rate` |
| Functions | `snake_case` | `make_features()` |
| Classes | `PascalCase` | `FeatureEngineer` |
| Constants | `UPPER_SNAKE` | `MAX_ITER = 1000` |
| Private | `_leading_underscore` | `_helper()` |

**Be descriptive:** `learning_rate` ✅, `auc` ✅ (standard abbrev), `lr` ❌
(ambiguous).

---

## 9. ML-Specific Guidelines

Kept deliberately small — stdlib only, no external tracking/versioning tools.

### Reproducibility (Beyond `np.random.seed`)
```python
import os
import random
import sys

import numpy as np
import lightgbm as lgb
import pandas as pd

RANDOM_STATE = 42

# Set every seed — including the hash seed
os.environ["PYTHONHASHSEED"] = str(RANDOM_STATE)
random.seed(RANDOM_STATE)
np.random.seed(RANDOM_STATE)

# LightGBM-specific: bit-exact reproducibility requires both flags
lgb_params = {
    "seed": RANDOM_STATE,
    "deterministic": True,
    "force_row_wise": True,
    # ... other params
}

# Log versions next to results for future reproduction
print(f"Python: {sys.version.split()[0]}")
print(f"Pandas: {pd.__version__}")
print(f"LightGBM: {lgb.__version__}")
```

### Cross-Validation for Sequential / Grouped Data
F1 lap data is sequential and naturally grouped by race. A plain
`StratifiedKFold` leaks future laps of the same race into training.
```python
from sklearn.model_selection import GroupKFold, TimeSeriesSplit

# Group-aware: every lap of a race stays in the same fold
cv = GroupKFold(n_splits=5)
groups = df["race_id"]  # or season + round
for train_idx, val_idx in cv.split(X, y, groups=groups):
    ...

# Strict time order (e.g. predicting future seasons from past ones)
cv = TimeSeriesSplit(n_splits=5)
```
Use plain `StratifiedKFold` only when rows are genuinely independent.

### Data Handling
```python
# Don't mutate raw data in place
def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    ...
    return df

# Separate features/target early
FEATURES = [c for c in df.columns if c not in EXCLUDE]
X: np.ndarray = df[FEATURES].values
y: np.ndarray = df[TARGET].values
```

### Lightweight Config via `dataclass`
No Hydra, no OmegaConf — a frozen dataclass is enough for a small project
and serialises trivially.
```python
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class TrainConfig:
    model: str = "lgbm"
    n_folds: int = 5
    learning_rate: float = 0.03
    num_leaves: int = 64
    seed: int = RANDOM_STATE

cfg = TrainConfig()
```

### Persisting Experiments (No External Tracker)
Save the config, CV scores, and metadata next to the model artefact:
```python
import json
from datetime import datetime

import joblib

results = {
    "model_name": "lgbm_v2",
    "config": asdict(cfg),
    "params": lgb_params,
    "cv_mean": 0.9496,
    "cv_std": 0.0008,
    "timestamp": datetime.now().isoformat(),
    "versions": {
        "pandas": pd.__version__,
        "lightgbm": lgb.__version__,
    },
}

joblib.dump(model, "models/02_lgbm/model.pkl")
with open("models/02_lgbm/results.json", "w") as f:
    json.dump(results, f, indent=2)
```
This is sufficient for a single-developer project. Adopt MLflow / W&B / DVC
only if the experiment count or team size grows enough to need them.

---

## 10. Error Handling

```python
# Fail early with a clear message
if "target" not in df.columns:
    raise ValueError("DataFrame must contain a 'target' column")

# Catch specific exceptions
try:
    data = pd.read_csv(path)
except FileNotFoundError:
    logger.error(f"Data file not found: {path}")
    raise
except pd.errors.EmptyDataError:
    logger.error(f"Data file is empty: {path}")
    raise
```

**Don't:**
```python
try:
    ...
except:  # swallows everything, including KeyboardInterrupt
    pass
```

---

## 11. Performance & Memory

```python
import gc

# Free large objects when done with them
del model, train_data, valid_data
gc.collect()

# Pick efficient dtypes
df["category"] = df["category"].astype("category")
df["flag"] = df["flag"].astype("bool")

# Vectorise — never iterate row-by-row
# Bad:  for i in range(len(df)): df.iloc[i, ...]
# Good: df["new"] = df["a"] / df["b"]
```

---

## 12. File Structure

```
project/
├── data/                    # Data files (gitignored)
├── models/                  # Trained models + per-experiment CSV/JSON outputs
├── notebooks/               # Exploration notebooks
├── src/                     # Reusable code (if grown into a package)
├── tests/                   # pytest tests (if any)
├── CODING_GUIDELINES.md     # This file
├── pyproject.toml           # Project + Ruff/mypy/pytest config
├── requirements.txt         # Pinned deps (kept for `pip install -r`)
├── setup_venv.sh            # One-shot venv bootstrap
├── .gitignore
└── README.md
```

`pyproject.toml` is the modern home for tool config (Ruff, mypy, pytest). It
can coexist with `requirements.txt`; the latter stays for `pip install -r`
compatibility.

---

## 13. Git & Collaboration

**Commit messages — Conventional Commits:**
- `feat: add tyre life ratio feature`
- `fix: handle missing values in test set`
- `refactor: extract feature engineering to utils`
- `docs: update coding guidelines`
- `perf: switch ETL pipeline to Polars`

**Branch naming:** `feat/short-description`, `fix/issue-123`.

**Pull requests:** link to issue, describe changes, note breaking changes.

---

## 14. Pre-Commit Checklist

- [ ] File has a docstring explaining its purpose
- [ ] Public functions have Google-style docstrings
- [ ] `ruff check` and `ruff format` pass
- [ ] No unused imports / variables (Ruff catches these)
- [ ] No hard-coded paths (use args / config)
- [ ] Seeds **and** LGBM determinism flags set
- [ ] DataFrames copied before modification
- [ ] Config + CV scores saved alongside model artefacts
- [ ] Tests pass (if applicable)

---

## 15. Tools

The 2026 stack is consolidated: **Ruff** alone replaces Black, Flake8, isort,
pyupgrade, and pydocstyle, runs 10–100× faster, and is configured in
`pyproject.toml`.

```bash
# Lint + auto-fix (replaces flake8 + isort + pyupgrade)
ruff check --fix .

# Format (replaces black)
ruff format .

# Type checking — optional, useful at module boundaries
mypy src/
```

### Minimal `pyproject.toml` Tool Config
```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "PD", "NPY", "RUF"]
ignore = ["E501"]  # ruff format handles line length

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
```

### Optional: `uv` Instead of `pip` + `venv`
`uv` is a single Rust binary that replaces `pip`, `virtualenv`, and `pyenv`,
typically 10–100× faster. Drop-in compatible with the existing
`requirements.txt`:
```bash
uv venv                              # creates .venv
uv pip install -r requirements.txt   # same semantics as pip
uv run python script.py              # run inside the env
```
The current `setup_venv.sh` workflow keeps working unchanged — `uv` is purely
an optional speedup.

---

*Last updated: 2026-05-05*
