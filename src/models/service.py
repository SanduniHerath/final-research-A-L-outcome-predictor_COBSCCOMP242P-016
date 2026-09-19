"""System part 1 - prediction for one student (Phase 9).

Uses the networks chosen in Phase 6 and tested once in Phase 7, unchanged:

* Z-score: the Stage-2 single-task MLP. It is shown as a RANGE built from the validation residuals
  (``prediction.interval_level`` in configs/app.yaml), never as one exact number.
* Z-score band, university group, degree category: the multi-output MLP, with the temperatures
  fitted on the validation set in Phase 6 (temperature scaling, one network, no ensemble).

Each classification answer carries a plain confidence message chosen from the Phase 7 test
calibration of the chosen system, so the wording follows measured reliability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from typing import Any

import numpy as np
import pandas as pd

from src.explain.core import P6, ChosenSystem, display_name
from src.models import student
from src.models.cv import band_edges
from src.models.data import class_names
from src.utils.config import load_config, resolve_path

CLASS_TASKS = ["zscore_band", "university_group", "degree_category"]
CHOSEN = "chosen_system"


def apply_temperature(proba: np.ndarray, t: float) -> np.ndarray:
    """Temperature-scaled probabilities (same formula as Phase 7)."""
    z = np.log(np.clip(proba, 1e-12, 1)) / t
    z = z - z.max(axis=1, keepdims=True)
    return np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)


def calibration_level(row: pd.Series) -> str:
    """'reliable', 'rough' or 'very_rough' from a Phase 7 calibration row."""
    if not row["brier_skill_ci_lower_above_0"]:
        return "very_rough"
    return "reliable" if row["ece_meets_max"] else "rough"


def calibration_levels() -> dict[str, str]:
    """Confidence level of each classification task, from the Phase 7 test results."""
    reports = resolve_path(load_config("project")["paths"]["reports"])
    table = pd.read_csv(reports / "phase07" / "calibration.csv")
    chosen = table[(table["system"] == CHOSEN) & (table["scaled"])]
    return {r["target"]: calibration_level(r) for _, r in chosen.iterrows()}


@dataclass
class Predictor:
    """Loads the chosen system once and predicts for one student at a time."""

    system: ChosenSystem
    temperatures: dict[str, float]
    residual_quantiles: tuple[float, float]
    levels: dict[str, str]
    cfg: dict[str, Any]

    @classmethod
    def load(cls) -> Predictor:
        """Load networks, pipeline, temperatures, validation residual range and calibration."""
        cfg = load_config("app")["prediction"]
        system = ChosenSystem.load()
        decisions = json.loads((P6 / "decisions.json").read_text("utf-8"))
        selected = decisions["architecture"]["selected"]
        temps = json.loads((P6 / "temperatures_seed0.json").read_text("utf-8"))[selected]
        processed = resolve_path(load_config("project")["paths"]["processed"])
        val = pd.read_csv(processed / "features_validation.csv")
        pred = system.task_function("zscore")(val[system.columns].to_numpy(np.float32))
        residual = val["zscore"].to_numpy() - pred
        tail = (1 - cfg["interval_level"]) / 2
        low, high = np.quantile(residual, [tail, 1 - tail])
        return cls(system, temps, (float(low), float(high)), calibration_levels(), cfg)

    @cached_property
    def names(self) -> dict[str, list[str]]:
        """Class names per task; bands get their student-facing labels."""
        names = class_names()
        names["zscore_band"] = list(self.cfg["band_labels"])
        return names

    def features(self, profile: dict[str, Any]) -> np.ndarray:
        """The 34 model inputs for one student."""
        return student.to_features(profile, self.system.pipeline, self.system.columns)

    def raw(self, x: np.ndarray) -> dict[str, np.ndarray]:
        """Z-score and temperature-scaled class probabilities for feature rows ``x``."""
        out = {"zscore": self.system.task_function("zscore")(x)}
        for task in CLASS_TASKS:
            p = self.system.task_function(task)(x)
            out[task] = apply_temperature(p, self.temperatures[task])
        return out

    def z_range(self, z: float) -> tuple[float, float]:
        """The validation-residual range around a predicted Z-score."""
        low, high = self.residual_quantiles
        return z + low, z + high

    def _classes(self, task: str, proba: np.ndarray) -> dict[str, Any]:
        order = np.argsort(-proba)
        top = float(proba[order[0]])
        level = self.levels[task]
        return {
            "probabilities": {self.names[task][i]: round(float(proba[i]), 4) for i in order},
            "most_likely": self.names[task][order[0]],
            "top_probability": round(top, 4),
            "model_is_sure": top >= self.cfg["sure_threshold"],
            "calibration": level,
            "confidence_message": self.cfg["confidence_messages"][level],
        }

    def predict(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Everything the 'My prediction' page needs for one student."""
        x = self.features(profile)
        out = self.raw(x)
        z = float(out["zscore"][0])
        low, high = self.z_range(z)
        edges = band_edges()
        band_of_z = int(np.searchsorted(edges, z, side="right"))
        level = int(round(self.cfg["interval_level"] * 10))
        result: dict[str, Any] = {
            "zscore": {
                "predicted": round(z, 2),
                "range_low": round(low, 2),
                "range_high": round(high, 2),
                "range_level": self.cfg["interval_level"],
                "message": (
                    f"Our best guess is a Z-score of about {z:.2f}. When we checked the model on "
                    f"students it had not seen, {level} out of 10 got a real Z-score within the "
                    f"same distance of the guess, so we show {low:.2f} to {high:.2f}."
                ),
                "below_data_range": low < self.cfg["lowest_z_in_data"],
            },
            "zscore_band": self._classes("zscore_band", out["zscore_band"][0]),
            "degree_category": self._classes("degree_category", out["degree_category"][0]),
        }
        result["zscore_band"]["band_edges"] = [round(e, 2) for e in edges]
        result["zscore_band"]["band_of_predicted_z"] = self.names["zscore_band"][band_of_z]
        uni = self._classes("university_group", out["university_group"][0])
        k = self.cfg["university_top_k"]
        uni["top_k"] = list(uni["probabilities"])[:k]
        result["university_group"] = uni
        if result["zscore"]["below_data_range"]:
            result["zscore"]["warning"] = (
                "Everyone in our survey got into university, and the lowest Z-score among them was "
                f"{self.cfg['lowest_z_in_data']:.2f}. For results this low, the model has no "
                "examples, so the real result could be lower than shown."
            )
        return result


def feature_names(columns: list[str]) -> list[str]:
    """Plain-language names of the model inputs."""
    return [display_name(c) for c in columns]


__all__ = ["CLASS_TASKS", "Predictor", "apply_temperature", "calibration_levels", "feature_names"]
