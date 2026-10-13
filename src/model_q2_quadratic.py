"""Question 2 quadratic and Question 3 energy-storage models."""
from __future__ import annotations

import gurobipy as gp
from gurobipy import GRB

from .model import ConsumerModel, Results


class QuadraticDisutilityModel(ConsumerModel):
    """Minimise procurement cost plus quadratic deviation from a reference load."""

    def _objective(self):
        d = self.data
        return gp.quicksum(
            d.pv_marginal_cost * self.var["pv"][t]
            + (d.import_tariff + d.energy_price[t]) * self.var["import"][t]
            - (d.energy_price[t] - d.export_tariff) * self.var["export"][t]
            + d.quadratic_disutility
            * (self.var["load"][t] - d.reference_load[t]) ** 2
            for t in self.T
        )

    def _extract_results(self, status: str) -> Results:
        results = super()._extract_results(status)
        deviation = results.hourly["load"] - results.hourly["reference_load"]
        results.meta.update(
            disutility=float(
                self.data.quadratic_disutility * (deviation**2).sum()
            ),
            total_deviation=float(deviation.abs().sum()),
            procurement_cost=float(
                results.objective
                - self.data.quadratic_disutility * (deviation**2).sum()
            ),
            binding_hours=int((deviation.abs() > 1e-6).sum()),
        )
        return results


class MinimumDailyEnergyModel(QuadraticDisutilityModel):
    """Question 3: quadratic disutility with a minimum daily energy requirement."""

    def _add_constraints(self) -> None:
        super()._add_constraints()
        if self.data.min_daily_energy_kWh is None:
            raise ValueError(
                f"{self.data.question} does not define min_daily_energy_kWh."
            )
        self.con["minimum_daily_energy"] = self.m.addConstr(
            gp.quicksum(self.var["load"][t] for t in self.T)
            >= self.data.min_daily_energy_kWh,
            name="minimum_daily_energy",
        )


class BatteryMinimumDailyEnergyModel(MinimumDailyEnergyModel):
    """Question 3 with a battery and no terminal state-of-charge requirement."""

    def _add_variables(self) -> None:
        super()._add_variables()
        self.var["charge"] = self.m.addVars(
            self.T, lb=0, vtype=GRB.CONTINUOUS, name="charge"
        )
        self.var["discharge"] = self.m.addVars(
            self.T, lb=0, vtype=GRB.CONTINUOUS, name="discharge"
        )
        self.var["soc"] = self.m.addVars(
            self.T, lb=0, vtype=GRB.CONTINUOUS, name="soc"
        )

    def _power_balance(self, t: int):
        return super()._power_balance(t) - self.var["charge"][t] + self.var["discharge"][t]

    def _add_constraints(self) -> None:
        super()._add_constraints()
        d = self.data
        if d.battery_capacity_kWh is None:
            raise ValueError(f"{d.question} does not define battery parameters.")
        self.con["charge_max"] = self.m.addConstrs(
            (self.var["charge"][t] <= d.battery_max_charge_kW for t in self.T),
            name="charge_max",
        )
        self.con["discharge_max"] = self.m.addConstrs(
            (self.var["discharge"][t] <= d.battery_max_discharge_kW for t in self.T),
            name="discharge_max",
        )
        self.con["soc_max"] = self.m.addConstrs(
            (self.var["soc"][t] <= d.battery_capacity_kWh for t in self.T),
            name="soc_max",
        )
        self.con["soc_balance"] = self.m.addConstrs(
            (
                self.var["soc"][t]
                == (
                    d.battery_initial_soc_kWh
                    if t == 0
                    else self.var["soc"][t - 1]
                )
                + d.battery_charging_efficiency * self.var["charge"][t]
                - self.var["discharge"][t] / d.battery_discharging_efficiency
                for t in self.T
            ),
            name="soc_balance",
        )
