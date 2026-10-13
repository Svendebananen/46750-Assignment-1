"""Question 2 linear-disutility model."""
from __future__ import annotations

import gurobipy as gp
from gurobipy import GRB

from .model import ConsumerModel, Results


class LinearDisutilityModel(ConsumerModel):
    """Minimise procurement cost plus absolute deviation from a reference load."""

    def _add_variables(self) -> None:
        super()._add_variables()
        self.var["deviation"] = self.m.addVars(
            self.T, lb=0, vtype=GRB.CONTINUOUS, name="deviation"
        )

    def _objective(self):
        d = self.data
        return gp.quicksum(
            d.pv_marginal_cost * self.var["pv"][t]
            + (d.import_tariff + d.energy_price[t]) * self.var["import"][t]
            - (d.energy_price[t] - d.export_tariff) * self.var["export"][t]
            + d.linear_disutility * self.var["deviation"][t]
            for t in self.T
        )

    def _add_constraints(self) -> None:
        super()._add_constraints()
        d = self.data
        self.con["deviation_pos"] = self.m.addConstrs(
            (
                self.var["load"][t]
                - d.reference_load[t]
                - self.var["deviation"][t]
                <= 0
                for t in self.T
            ),
            name="deviation_pos",
        )
        self.con["deviation_neg"] = self.m.addConstrs(
            (
                d.reference_load[t]
                - self.var["load"][t]
                - self.var["deviation"][t]
                <= 0
                for t in self.T
            ),
            name="deviation_neg",
        )

    def _extract_results(self, status: str) -> Results:
        results = super()._extract_results(status)
        results.meta.update(
            disutility=float(
                self.data.linear_disutility * results.hourly["deviation"].sum()
            ),
            total_deviation=float(results.hourly["deviation"].sum()),
            procurement_cost=float(
                results.objective
                - self.data.linear_disutility * results.hourly["deviation"].sum()
            ),
            binding_hours=int((results.hourly["deviation"] > 1e-6).sum()),
        )
        return results
