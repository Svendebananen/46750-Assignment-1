# 46750 - Assignment 1: Demand-Side Flexibility in Active Distribution Grids

This repository contains the Python implementation and input data for Group 20's
Assignment 1 in *46750 - Optimization in Modern Power Systems* at DTU. The program
loads one case, builds the corresponding Gurobi optimisation model, solves it, and
saves numerical results and figures.

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

### `appliance_params.json`

This is a shared catalogue. Case files refer to catalogue entries by ID.

- `DERs`: PV ID and type, peak power (`max_power_kW`), marginal production cost,
  current-day profile and next-day profile. Profiles are dimensionless ratios in
  `[0, 1]`; available energy is `max_power_kW * profile` in kWh per hour.
- `loads`: hourly minimum and maximum consumption in kWh/h; Question 1 utility in
  DKK/kWh; linear disutility in DKK/kWh; quadratic disutility in DKK/kWh²;
  minimum daily energy in kWh; and the reference-load profile ratio.
- `storages`: battery capacity in kWh, charge/discharge limits in kW, efficiencies,
  and initial SoC ratio. Efficiencies are fractions, not percentages.
- `heat_pumps`: unused in this assignment and currently `null`.

### `bus_params.json`

Each bus defines import and export tariffs in DKK/kWh, 24 current-day energy prices,
24 next-day prices, and optional import/export limits. `null` means no limit is
provided. Current model code does not enforce the optional limits.

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
- `list_questions(data_dir=...)` returns the available case names.
- `InputData.summary()` returns a human-readable overview. Array attributes such as
  `energy_price`, `pv_available` and `reference_load` use the units stated in their
  names and comments in `src/data_loader.py`.
- `FlexibleConsumerModel`, `LinearDisutilityModel`, `QuadraticDisutilityModel`,
  `MinimumDailyEnergyModel` and `BatteryMinimumDailyEnergyModel` build and solve
  the formulations listed above. Call `.build()` before `.solve()`.
- `Results.hourly` is a pandas DataFrame containing hourly primal variables, prices,
  available PV, reference load where applicable, and hourly dual columns named
  `dual_<constraint>`. `Results.duals` contains scalar constraint duals.
- `Results.save(folder, tag="")` writes `<question>[_<tag>]_hourly.csv` and
  `<question>[_<tag>]_summary.txt`.
- `plot_inputs`, `plot_schedule`, `plot_duals` and `plot_scenario_comparison` return
  Matplotlib figures and optionally save them with `save_to`.

## 7. Sensitivity helpers

The helpers in `src/scenarios.py` derive a new `InputData` without changing the base
object:

- `scale_prices(data, factor, keep_mean=False)` scales DKK/kWh prices.
- `shift_prices(data, delta)` adds a DKK/kWh price offset.
- `roll_prices(data, hours)` shifts the 24-hour price profile.
- `set_tariffs(data, import_tariff=None, export_tariff=None)` overrides DKK/kWh tariffs.
- `scale_pv(data, factor)` scales available PV while keeping the profile ratio in `[0, 1]`.
- `set_load_preferences(...)` overrides hourly kWh/h bounds or minimum daily kWh.
- `Set_quadratic_disutility(data, value)` overrides the quadratic coefficient in DKK/kWh².
- `Set_capacity(data, value)` overrides battery capacity in kWh.

The command-line `--scenarios` option always includes the base case. It adds minimum
energy and quadratic-disutility scenarios for `Q3`, and price-spread and capacity
scenarios for `Q3_battery`. Other cases currently run only the base case when the
flag is supplied.

## 8. Outputs

For a base run, `results/<question>/` contains:

- `inputs.png`: prices, tariffs, available PV and load preferences.
- `schedule.png`: optimal load, PV, grid exchange and battery state where applicable.
- `duals.png`: hourly dual variables and price signals.
- `<question>_hourly.csv`: hourly solution values.
- `<question>_summary.txt`: solver status, objective, scalar duals and battery metadata.

Scenario runs add one CSV, TXT and schedule PNG per scenario plus
`scenarios_cost.png`. The `results/` directory is generated output and is not part of
the source data.
