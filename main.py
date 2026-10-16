"""Entry point: load one question's data, build and solve the model, save results and figures.

    python main.py                          # base case of Q1_caseA
    python main.py --question Q2_linear     # another case
    python main.py --scenarios              # also run the example sensitivity scenarios

Results (CSV, TXT, PNG) are written to ``results/<question>/``. Extend ``run_scenarios``
with your own scenarios, or add a new function per question, as your analysis grows.
"""
from __future__ import annotations

import argparse
from pathlib import Path

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
from src.scenarios import Set_capacity, Set_quadratic_disutility, scale_prices, scale_pv, set_tariffs, set_load_preferences

RESULTS_DIR = Path(__file__).resolve().parent / "results"

MODEL_TYPES = {
    "Q2_linear": LinearDisutilityModel,
    "Q2_quadratic": QuadraticDisutilityModel,
    "Q3": MinimumDailyEnergyModel,
    "Q3_battery": BatteryMinimumDailyEnergyModel,
}


def build_model(question: str, data):
    """Create the model formulation associated with a data case."""
    model_type = MODEL_TYPES.get(question, FlexibleConsumerModel)
    return model_type(data).build()


def run_base_case(question: str, out: Path, show: bool) -> Results | None:
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


def run_scenarios(question: str, out: Path) -> dict[str, Results]:
    """Example sensitivity analysis. Replace with the scenarios you design in Question 1.g."""
    base = load_question(question)
    scenarios = {
        "base": base,
        # "flat_prices": scale_prices(base, factor=0.0, keep_mean=True),
        # "double_spread": scale_prices(base, factor=2.0, keep_mean=True),
        # "no_tariffs": set_tariffs(base, import_tariff=0.0, export_tariff=0.0),
        # "no_pv": scale_pv(base, factor=0.0),
        #"Increase_E_min_20": set_load_preferences(base, min_daily_energy_kWh=20.0),
        #"Increase_E_min_30": set_load_preferences(base, min_daily_energy_kWh=30.0),
        #"Increase_E_min_40": set_load_preferences(base, min_daily_energy_kWh=40.0),
        #"Increase_E_min_50": set_load_preferences(base, min_daily_energy_kWh=50.0),
        #"Increase_E_min_60": set_load_preferences(base, min_daily_energy_kWh=60.0),
        #"Decrease_quadratic_disutility_to_0": Set_quadratic_disutility(base, value=0.0),
        #"Decrease_quadratic_disutility_to_0_125": Set_quadratic_disutility(base, value=0.125),
        #"Decrease_quadratic_disutility_to_0_25": Set_quadratic_disutility(base, value=0.25),
        #"Decrease_quadratic_disutility_to_0_5": Set_quadratic_disutility(base, value=0.5),
        #"Decrease_quadratic_disutility_to_1": Set_quadratic_disutility(base, value=1),
        #"Decrease_quadratic_disutility_to_2": Set_quadratic_disutility(base, value=2),
        #"Decrease_quadratic_disutility_to_4": Set_quadratic_disutility(base, value=4),
        #"Decrease_quadratic_disutility_to_6": Set_quadratic_disutility(base, value=6),
        "change_in_price_varible_mean" : scale_prices( base, 0, keep_mean= True),
        "change_in_price_varible_50%" : scale_prices( base, 0.50, keep_mean= True),
        "change_in_price_varible_150%" : scale_prices( base, 1.5, keep_mean= True),
        "change_in_price_varible_300%" : scale_prices( base, 3, keep_mean= True),
        "change_in_price_varible_500%" : scale_prices( base, 5, keep_mean= True),
        "change_in_price_varible_1000%" : scale_prices( base, 10, keep_mean= True),
        "Capacity_for_the_battery_1" : Set_capacity(base, 1),
        "Capacity_for_the_battery_2" : Set_capacity(base, 2),
        "Capacity_for_the_battery_3" : Set_capacity(base, 3),
        "Capacity_for_the_battery_6" : Set_capacity(base, 6),
        "Capacity_for_the_battery_8" : Set_capacity(base, 8),
        "Capacity_for_the_battery_10" : Set_capacity(base, 10),
        "Capacity_for_the_battery_14" : Set_capacity(base, 14)


    }
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
