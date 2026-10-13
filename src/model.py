"""Shared optimisation model infrastructure and the Question 1 formulation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import gurobipy as gp
import pandas as pd
from gurobipy import GRB

from .data_loader import InputData


@dataclass
class Results:
    """Primal and dual solution of one model run."""

    question: str
    status: str
    objective: float
    hourly: pd.DataFrame
    duals: dict[str, float] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    def save(self, folder: Path | str, tag: str = "") -> None:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        stem = f"{self.question}{'_' + tag if tag else ''}"
        self.hourly.to_csv(folder / f"{stem}_hourly.csv", index_label="hour")
        with open(folder / f"{stem}_summary.txt", "w", encoding="utf-8") as f:
            f.write(f"status    : {self.status}\nobjective : {self.objective:.4f} DKK\n")
            for name, value in self.duals.items():
                f.write(f"dual[{name}] : {value:.4f}\n")

    def __str__(self) -> str:
        daily = ", ".join(
            f"{name}={self.hourly[name].sum():.1f}"
            for name in ("import", "export", "load", "pv")
            if name in self.hourly
        )
        return (
            f"status: {self.status} | objective: {self.objective:.2f} DKK\n"
            f"daily totals (kWh): {daily}"
            + (f"\nduals: {self.duals}" if self.duals else "")
        )


def _dual(constraint) -> float:
    return constraint.QCPi if isinstance(constraint, gp.QConstr) else constraint.Pi


_STATUS = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.SUBOPTIMAL: "SUBOPTIMAL",
    GRB.NUMERIC: "NUMERIC",
    GRB.INTERRUPTED: "INTERRUPTED",
}


def _status_name(code: int) -> str:
    return _STATUS.get(code, f"STATUS_{code}")


class ConsumerModel:
    """Base class containing the common model lifecycle and physical constraints."""

    def __init__(
        self,
        data: InputData,
        name: str = "flexible_consumer",
        verbose: bool = False,
    ):
        self.data = data
        self.T = range(data.n_hours)
        self.m = gp.Model(name)
        self.m.Params.OutputFlag = 1 if verbose else 0
        self.m.Params.QCPDual = 1
        self.var: dict[str, gp.tupledict] = {}
        self.con: dict[str, gp.tupledict | gp.Constr] = {}

    def build(self) -> "ConsumerModel":
        self._add_variables()
        self.m.setObjective(self._objective(), self._objective_sense())
        self._add_constraints()
        self.m.update()
        return self

    def _add_variables(self) -> None:
        self.var["import"] = self.m.addVars(
            self.T, lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS, name="import"
        )
        self.var["export"] = self.m.addVars(
            self.T, lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS, name="export"
        )
        self.var["load"] = self.m.addVars(
            self.T, lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS, name="load"
        )
        self.var["pv"] = self.m.addVars(
            self.T, lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS, name="pv"
        )

    def _objective(self):
        raise NotImplementedError

    def _objective_sense(self) -> int:
        return GRB.MINIMIZE

    def _power_balance(self, t: int):
        return (
            self.var["pv"][t]
            + self.var["import"][t]
            - self.var["load"][t]
            - self.var["export"][t]
        )

    def _add_constraints(self) -> None:
        d, m, T = self.data, self.m, self.T
        self.con["power_balances"] = m.addConstrs(
            (self._power_balance(t) == 0 for t in T), name="power_balances"
        )
        self.con["load_min"] = m.addConstrs(
            (d.load_min_kWh - self.var["load"][t] <= 0 for t in T),
            name="load_min",
        )
        self.con["load_max"] = m.addConstrs(
            (self.var["load"][t] - d.load_max_kWh <= 0 for t in T),
            name="load_max",
        )
        self.con["nonnegative_import"] = m.addConstrs(
            (-self.var["import"][t] <= 0 for t in T), name="nonnegative_import"
        )
        self.con["nonnegative_export"] = m.addConstrs(
            (-self.var["export"][t] <= 0 for t in T), name="nonnegative_export"
        )
        self.con["nonnegative_pv"] = m.addConstrs(
            (-self.var["pv"][t] <= 0 for t in T), name="nonnegative_pv"
        )
        self.con["pv_max"] = m.addConstrs(
            (self.var["pv"][t] - d.pv_available[t] <= 0 for t in T),
            name="pv_max",
        )

    def solve(self) -> Results:
        self.m.update()
        if self.m.NumConstrs == 0 and self.m.NumQConstrs == 0:
            raise NotImplementedError("Build the model before solving it.")
        self.m.optimize()
        status = _status_name(self.m.Status)
        if self.m.Status != GRB.OPTIMAL:
            raise RuntimeError(
                f"Optimisation ended with status {status}. "
                "Check the model (m.computeIIS() helps for infeasibility)."
            )
        return self._extract_results(status)

    def _extract_results(self, status: str) -> Results:
        d, T = self.data, list(self.T)
        hourly = pd.DataFrame(index=pd.Index(T, name="hour"))
        hourly["price"] = d.energy_price
        hourly["pv_available"] = d.pv_available
        if d.reference_load is not None:
            hourly["reference_load"] = d.reference_load

        for name, variable in self.var.items():
            hourly[name] = [variable[t].X for t in T]

        duals: dict[str, float] = {}
        for name, constraint in self.con.items():
            try:
                if isinstance(constraint, gp.tupledict):
                    hourly[f"dual_{name}"] = [_dual(constraint[t]) for t in T]
                else:
                    duals[name] = _dual(constraint)
            except (AttributeError, gp.GurobiError):
                pass

        load = hourly["load"]
        meta = {
            "scalar_variables": {},
            "daily_energy": float(load.sum()),
            "procurement_cost": float(
                (
                    d.pv_marginal_cost * hourly["pv"]
                    + (d.import_tariff + d.energy_price) * hourly["import"]
                    - (d.energy_price - d.export_tariff) * hourly["export"]
                ).sum()
            ),
        }
        return Results(
            question=d.question,
            status=status,
            objective=self.m.ObjVal,
            hourly=hourly,
            duals=duals,
            meta=meta,
        )


class FlexibleConsumerModel(ConsumerModel):
    """Question 1: maximise consumption utility minus procurement cost."""

    def _objective(self):
        d = self.data
        return gp.quicksum(
            d.consumption_utility * self.var["load"][t]
            - d.pv_marginal_cost * self.var["pv"][t]
            - (d.import_tariff + d.energy_price[t]) * self.var["import"][t]
            + (d.energy_price[t] - d.export_tariff) * self.var["export"][t]
            for t in self.T
        )

    def _objective_sense(self) -> int:
        return GRB.MAXIMIZE

    def _extract_results(self, status: str) -> Results:
        results = super()._extract_results(status)
        if self.data.consumption_utility is None:
            raise ValueError(
                f"{self.data.question} does not define consumption_utility."
            )
        results.meta["utility"] = float(
            self.data.consumption_utility * results.hourly["load"].sum()
        )
        return results
