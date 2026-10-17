"""Entry point: load one question's data, build and solve the model, save results and figures.

    python main.py                          # base case of Q1_caseA
    python main.py --question Q2_linear     # another case
    python main.py --scenarios              # also run the example sensitivity scenarios

Results (CSV, TXT, PNG) are written to ``results/<question>/``. ``--scenarios`` runs
the sensitivity cases defined for the selected question.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

from src.data_loader import load_question, list_questions
from src.model import (
    BatteryMinimumDailyEnergyModel,
    FlexibleConsumerModel,
    LinearDisutilityModel,
    MinimumDailyEnergyModel,
    QuadraticDisutilityModel,
    Results,
)
from src.plotting import plot_duals, plot_inputs, plot_scenario_comparison, plot_schedule
from src.scenarios import Set_capacity, Set_linear_disutility, Set_quadratic_disutility, scale_prices, set_load_preferences

RESULTS_DIR = Path(__file__).resolve().parent / "results"

MODEL_TYPES = {
    "Q2_linear": LinearDisutilityModel,
    "Q2_quadratic": QuadraticDisutilityModel,
    "Q3": MinimumDailyEnergyModel,
    "Q3_battery": BatteryMinimumDailyEnergyModel,
}


def build_model(question: str, data):
    """Build the model for ``question`` from validated ``InputData``.

    Parameters
    ----------
    question : str
        Case name such as ``"Q1_caseA"``.
    data : InputData
        Loaded case parameters, including prices in DKK/kWh and power or energy
        limits in their corresponding units.

    Returns
    -------
    ConsumerModel
        A built, unsolved Gurobi model.
    """
    model_type = MODEL_TYPES.get(question, FlexibleConsumerModel)
    return model_type(data).build()


def run_base_case(question: str, out: Path, show: bool) -> Results | None:
    """Solve one case, save its CSV/TXT results and save its PNG figures.

    Parameters
    ----------
    question : str
        Case name accepted by :func:`load_question`.
    out : Path
        Output directory.
    show : bool
        Whether to display Matplotlib figures after solving.

    Returns
    -------
    Results or None
        The optimal result, or ``None`` if a model is intentionally skipped.
    """
    data = load_question(question)
    print(data.summary(), "\n")
    plot_inputs(data, save_to=out / "inputs.png")

    model = build_model(question, data)
    try:
        results = model.solve()
    except NotImplementedError as e:
        print(f"[skipped] {e}")
        return None

    print(results, "\n")
    print()
    results.save(out)
    plot_schedule(results, data, save_to=out / "schedule.png")
    plot_duals(results, data, save_to=out / "duals.png")
    if show:
        plt.show()
    return results

def run_q2_sweep(question: str, out: Path) -> None:
    setter = Set_linear_disutility if question == "Q2_linear" else Set_quadratic_disutility
    base = load_question(question)
    rows = []
    for c in [0.50, 1.00, 1.40, 1.41, 1.50, 1.75, 2.09, 2.10, 2.50, 3.00]:
        r = build_model(question, setter(base, c)).solve()
        m = r.meta
        rows.append([c, m["procurement_cost"], m["disutility"], m["daily_energy"],
                     m["total_deviation"], m["binding_hours"]])
    table = pd.DataFrame(rows, columns=["c", "procurement", "disutility", "energy", "deviation", "binding_hours"])
    table.to_csv(out / f"{question}_sweep.csv", index=False)
    print(table.round(2).to_string(index=False))

def run_scenarios(question: str, out: Path) -> dict[str, Results]:
    """Run the sensitivity scenarios associated with ``question``.

    Every question includes the unmodified base case. Question-specific sensitivity
    cases are added only for Q2, Q3 and Q3_battery. Costs are in DKK and hourly energy
    quantities are in kWh.
    """
    base = load_question(question)
    scenarios = {"base": base}

    if question.startswith("Q2"):
        run_q2_sweep(question, out)
        return {}

    if question == "Q3":
        scenarios.update({
            "Increase_E_min_20": set_load_preferences(base, min_daily_energy_kWh=20.0),
            "Increase_E_min_30": set_load_preferences(base, min_daily_energy_kWh=30.0),
            "Increase_E_min_40": set_load_preferences(base, min_daily_energy_kWh=40.0),
            "Increase_E_min_50": set_load_preferences(base, min_daily_energy_kWh=50.0),
            "Increase_E_min_60": set_load_preferences(base, min_daily_energy_kWh=60.0),
            "Decrease_quadratic_disutility_to_0": Set_quadratic_disutility(base, value=0.0),
            "Decrease_quadratic_disutility_to_0_5": Set_quadratic_disutility(base, value=0.5),
            "Decrease_quadratic_disutility_to_1": Set_quadratic_disutility(base, value=1),
            "Decrease_quadratic_disutility_to_2": Set_quadratic_disutility(base, value=2),
            "Decrease_quadratic_disutility_to_4": Set_quadratic_disutility(base, value=4),
            "Decrease_quadratic_disutility_to_6": Set_quadratic_disutility(base, value=6),
            "Decrease_quadratic_disutility_to_8": Set_quadratic_disutility(base, value=8),
        })
    elif question == "Q3_battery":
        scenarios.update({
            "change_in_price_varible_mean": scale_prices(base, 0, keep_mean=True),
            "change_in_price_varible_50%": scale_prices(base, 0.50, keep_mean=True),
            "change_in_price_varible_150%": scale_prices(base, 1.5, keep_mean=True),
            "change_in_price_varible_300%": scale_prices(base, 3, keep_mean=True),
            "Capacity_for_the_battery_1": Set_capacity(base, 1),
            "Capacity_for_the_battery_2": Set_capacity(base, 2),
            "Capacity_for_the_battery_3": Set_capacity(base, 3),
            "Capacity_for_the_battery_6": Set_capacity(base, 6),
            "Capacity_for_the_battery_14": Set_capacity(base, 14),
        })

    runs: dict[str, Results] = {}
    for name, data in scenarios.items():
        model = build_model(question, data)
        results = model.solve()
        results.save(out, tag=name)
        runs[name] = results
        print(f"{name:>14}: cost {results.objective:8.2f} DKK | import {results.hourly['import'].sum():5.1f} kWh"
              f" | export {results.hourly['export'].sum():5.1f} kWh" f" | load {results.hourly['load'].sum():5.1f} kWh")
        plot_schedule(results, data, save_to=out / f"{name}_schedule.png")
    plot_scenario_comparison(runs, "objective", save_to=out / "scenarios_cost.png")
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--question", default="Q1_caseA", choices=list_questions(), help="data case to use")
    parser.add_argument("--scenarios", action="store_true", help="also run the example sensitivity scenarios")
    parser.add_argument("--show", action="store_true", help="open the figures in a window")
    args = parser.parse_args()

    out = RESULTS_DIR / args.question
    out.mkdir(parents=True, exist_ok=True)
    if not args.show:
        matplotlib.use("Agg")

    base = run_base_case(args.question, out, args.show)
    if args.scenarios and base is not None:
        run_scenarios(args.question, out)
    print(f"\nOutputs written to {out}")


if __name__ == "__main__":
    main()
