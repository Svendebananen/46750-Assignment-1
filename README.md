# 46750 - Assignment 1: Demand-Side Flexibility in Active Distribution Grids - Group 20

The repository follows the recommended structure given in class. If familiar with it. Steps 1 - 3 can be skipped. 

## 1. Requirements and setup

Python 3.11 is used by the conda environment. The project also works with a regular
Python virtual environment.

### Option A: pip and venv

```bash
python -m venv venv
source venv/bin/activate              # macOS / Linux
# venv\Scripts\activate.bat           # Windows cmd
# venv\Scripts\Activate.ps1           # Windows PowerShell
python -m pip install -r requirements.txt
```

### Option B: conda

```bash
conda env create -f environment.yaml
conda activate 46750-a1
```

The optimisation models use `gurobipy`. A working Gurobi installation and licence are
required. The restricted licence normally included with Gurobi is sufficient for these
small models; otherwise activate a DTU academic licence with `grbgetkey <your-key>`.

## 2. Quick start

Run the default case:

```bash
python main.py
```

The default is `Q1_caseA`. To select another case:

```bash
python main.py --question Q1_caseB
python main.py --question Q2_linear
python main.py --question Q2_quadratic
python main.py --question Q3
python main.py --question Q3_battery
```

Add the predefined sensitivity runs for Question 3 or the battery case:

```bash
python main.py --question Q3 --scenarios
python main.py --question Q3_battery --scenarios
```

Use `--show` to display plots interactively. Without `--show`, Matplotlib uses a
non-interactive backend and writes the figures to disk:

```bash
python main.py --question Q1_caseA --show
```

## 3. Repository structure

```text
main.py                  Command-line entry point and experiment orchestration
src/
  data_loader.py         JSON loading, validation and the InputData dataclass
  model.py               Optimisation models and the Results dataclass
  plotting.py            Input, schedule, dual and scenario plots
  scenarios.py           Pure helpers for deriving sensitivity cases
  __init__.py             Python package marker
data/
  appliance_params.json  Shared PV, flexible-load and battery catalogue
  bus_params.json        Shared prices, tariffs and optional grid limits
  params_Q1_caseA.json   Case-to-appliance composition
  params_Q1_caseB.json
  params_Q2_linear.json
  params_Q2_quadratic.json
  params_Q3.json
  params_Q3_battery.json
results/                 Generated outputs; ignored by git
requirements.txt         pip dependencies
environment.yaml         conda environment definition
LICENSE                   Repository licence
```

`data_loader.py` and `model.py` are the core modules. `plotting.py` only visualises
data or solved results. `scenarios.py` returns copies of `InputData`; it does not edit
the JSON files or mutate the base case.

## 4. Cases and model formulations

All cases use 24 hourly periods (`hour` 0 to 23), with a one-hour timestep.

| Case | Model | Purpose |
| --- | --- | --- |
| `Q1_caseA` | `FlexibleConsumerModel` | Maximise consumption utility minus procurement cost; PV cost is below utility. |
| `Q1_caseB` | `FlexibleConsumerModel` | Same formulation with the more expensive PV catalogue entry. |
| `Q2_linear` | `LinearDisutilityModel` | Minimise procurement cost plus linear absolute deviation from the reference load. |
| `Q2_quadratic` | `QuadraticDisutilityModel` | Minimise procurement cost plus quadratic deviation from the reference load. |
| `Q3` | `MinimumDailyEnergyModel` | Question 2 quadratic model with a minimum daily energy constraint. |
| `Q3_battery` | `BatteryMinimumDailyEnergyModel` | Q3 with battery charge, discharge, state of charge and a terminal SoC value. |

The shared model enforces power balance, load bounds, non-negative import/export/PV,
and the available-PV limit. Battery models additionally enforce charge/discharge
limits, SoC capacity and SoC balance. The optional `max_import_kW` and
`max_export_kW` fields are loaded, but are not currently enforced as constraints.

## 5. Input data

### `params_<case>.json`

Each case selects a consumer, its connection bus and appliance IDs:

```json
{
  "consumers": [{
    "consumer_id": "C_01_A",
    "connection_bus": "Bus1",
    "list_appliances": ["PV_01_A", "FL_01"]
  }],
  "hyperparameters": null
}
```

`Q3_battery` uses `hyperparameters.battery_end_soc_value_DKK_per_kWh`. This is a
terminal value in the objective, not a required final SoC. The initial SoC comes from
the battery catalogue; the final SoC remains a model decision.

## 6. Python API

Load data, solve a model and inspect the result:

```python
from src.data_loader import load_question
from src.model import FlexibleConsumerModel
from src.plotting import plot_schedule

data = load_question("Q1_caseA")
print(data.summary())

results = FlexibleConsumerModel(data).build().solve()
print(results)
print(results.hourly)  # pandas DataFrame: one row per hour
plot_schedule(results, data, save_to="results/example_schedule.png")
results.save("results/example")
```

### Main public objects and functions

- `load_question(question, data_dir=..., consumer_index=0)` returns validated
  `InputData`. `question` may be `Q1_caseA`, `params_Q1_caseA`, or
  `params_Q1_caseA.json`.
- `FlexibleConsumerModel`, `LinearDisutilityModel`, `QuadraticDisutilityModel`,
  `MinimumDailyEnergyModel` and `BatteryMinimumDailyEnergyModel` build and solve
  the formulations listed above. Call `.build()` before `.solve()`.

## 7. Sensitivity helpers

The helpers in `src/scenarios.py` derive a new `InputData` without changing the base
object:

- `Set_quadratic_disutility(data, value)` overrides the quadratic coefficient in DKK/kWh².
- `Set_capacity(data, value)` overrides battery capacity in kWh.

The command-line `--scenarios` option always includes the base case. It adds minimum
energy and quadratic-disutility scenarios for `Q3`, and price-spread and capacity
scenarios for `Q3_battery`. Other cases currently run only the base case when the
flag is supplied.

