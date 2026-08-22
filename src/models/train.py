"""One training loop for every architecture (Phase 6).

* Early stopping uses a held-out part of the rows being trained on (never the rows
  that are scored afterwards); the best weights are restored.
* The Z-score head learns the Z-score standardised with the training-part mean and SD.
* University group and degree category use balanced class weights from the training
  part only (Phase 5 rule).
* The multi-task variant learns its loss weights (Kendall, Gal & Cipolla, 2018).
* TabNet adds its sparsity regulariser, as in the original implementation.
* The autoencoder of ``ae_mlp`` is fitted on the training part only.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
from torch import nn

from src.models.data import ModelData
from src.models.networks import AutoEncoder, build_network, count_parameters

CLASS_TASKS = {"zscore_band", "university_group", "degree_category"}


@dataclass
class Fitted:
    """A trained network and everything needed to use and describe it."""

    name: str
    cfg: dict[str, Any]
    tasks: list[str]
    network: nn.Module
    z_mean: float
    z_sd: float
    best_epoch: int
    epochs_run: int
    seconds: float
    n_params: int
    history: list[dict[str, float]] = field(default_factory=list)
    autoencoder: AutoEncoder | None = None
    ae_history: list[dict[str, float]] = field(default_factory=list)


def set_seed(seed: int) -> None:
    """Seed torch and NumPy for one fit."""
    torch.manual_seed(seed)
    np.random.seed(seed)


def class_weight_tensor(labels: np.ndarray, n_classes: int) -> torch.Tensor:
    """Balanced weights n / (k * count); a class absent from these rows gets weight 0."""
    counts = np.bincount(labels, minlength=n_classes).astype(float)
    present = counts > 0
    weights = np.zeros(n_classes)
    weights[present] = counts.sum() / (present.sum() * counts[present])
    return torch.tensor(weights, dtype=torch.float32)


def to_batch(
    data: ModelData, idx: np.ndarray | None = None, codes: np.ndarray | None = None
) -> dict[str, torch.Tensor]:
    """Tensors for the rows ``idx`` (all rows if ``None``)."""
    sel = slice(None) if idx is None else idx
    batch = {"x": torch.from_numpy(codes[sel] if codes is not None else data.x[sel])}
    if data.district is not None:
        batch["district"] = torch.from_numpy(data.district[sel])
    if data.wide is not None:
        batch["wide"] = torch.from_numpy(data.wide[sel])
    return batch


def split_early_stopping(n: int, fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Random (fit, early-stopping) row indices."""
    order = np.random.default_rng(seed).permutation(n)
    n_es = max(2, round(fraction * n))
    return order[n_es:], order[:n_es]


def task_losses(
    out: dict[str, torch.Tensor], targets: dict[str, torch.Tensor], weights: dict[str, torch.Tensor]
) -> dict[str, torch.Tensor]:
    """Per-task losses: MSE for the standardised Z-score, (weighted) cross-entropy otherwise."""
    losses = {}
    for task, pred in out.items():
        if task == "zscore":
            losses[task] = nn.functional.mse_loss(pred, targets[task])
        else:
            losses[task] = nn.functional.cross_entropy(
                pred, targets[task], weight=weights.get(task)
            )
    return losses


def combine(
    losses: dict[str, torch.Tensor], network: nn.Module, name: str, cfg: dict[str, Any]
) -> torch.Tensor:
    """Total training loss for the architecture."""
    if name == "mtl":
        total = sum(
            torch.exp(-network.log_vars[t]) * loss + network.log_vars[t]
            for t, loss in losses.items()
        )
        total = total.squeeze()
    else:
        total = sum(losses.values())
    if name == "tabnet":
        total = total - cfg["lambda_sparse"] * network.last_sparsity_loss
    return total


def _targets_tensor(
    data: ModelData, idx: np.ndarray, tasks: list[str], z_mean: float, z_sd: float
) -> dict[str, torch.Tensor]:
    out = {}
    for task in tasks:
        values = data.targets[task][idx]
        if task == "zscore":
            out[task] = torch.from_numpy(((values - z_mean) / z_sd).astype(np.float32))
        else:
            out[task] = torch.from_numpy(values)
    return out


def fit_autoencoder(
    x: np.ndarray, fit_idx: np.ndarray, es_idx: np.ndarray, cfg: dict[str, Any], max_epochs: int
) -> tuple[AutoEncoder, list[dict[str, float]]]:
    """Fit the autoencoder on training rows only (reconstruction MSE, early stopping)."""
    ae = AutoEncoder(x.shape[1], cfg["ae_units"], cfg["bottleneck"])
    opt = torch.optim.Adam(ae.parameters(), lr=cfg["lr"], weight_decay=cfg.get("weight_decay", 0.0))
    xt = torch.from_numpy(x)
    best, best_state, bad, history = np.inf, copy.deepcopy(ae.state_dict()), 0, []
    for epoch in range(max_epochs):
        ae.train()
        perm = fit_idx[np.random.permutation(len(fit_idx))]
        for start in range(0, len(perm), cfg["batch_size"]):
            rows = perm[start : start + cfg["batch_size"]]
            loss = nn.functional.mse_loss(ae(xt[rows]), xt[rows])
            opt.zero_grad()
            loss.backward()
            opt.step()
        ae.eval()
        with torch.no_grad():
            es_loss = nn.functional.mse_loss(ae(xt[es_idx]), xt[es_idx]).item()
        history.append({"epoch": epoch + 1, "es_reconstruction_mse": es_loss})
        if es_loss < best - 1e-6:
            best, best_state, bad = es_loss, copy.deepcopy(ae.state_dict()), 0
        else:
            bad += 1
            if bad >= cfg["patience"]:
                break
    ae.load_state_dict(best_state)
    ae.eval()
    return ae, history


def fit(
    name: str,
    cfg: dict[str, Any],
    data: ModelData,
    tasks: list[str],
    seed: int,
    dims: dict[str, Any],
    max_epochs: int = 300,
    es_fraction: float = 0.10,
) -> Fitted:
    """Train one network on ``data`` and return it with its training history."""
    start = time.perf_counter()
    set_seed(seed)
    fit_idx, es_idx = split_early_stopping(len(data), es_fraction, seed)
    z = data.targets["zscore"][fit_idx]
    z_mean, z_sd = float(z.mean()), float(z.std() or 1.0)

    autoencoder, ae_history, codes = None, [], None
    if name == "ae_mlp":
        autoencoder, ae_history = fit_autoencoder(data.x, fit_idx, es_idx, cfg, max_epochs)
        with torch.no_grad():
            codes = autoencoder.encode(torch.from_numpy(data.x)).numpy()

    network = build_network(name, cfg, dims, tasks)
    opt = torch.optim.Adam(
        network.parameters(), lr=cfg["lr"], weight_decay=cfg.get("weight_decay", 0.0)
    )
    weights = {
        t: class_weight_tensor(data.targets[t][fit_idx], n)
        for t, n in (("university_group", 5), ("degree_category", 7))
        if t in tasks
    }
    es_batch = to_batch(data, es_idx, codes)
    es_targets = _targets_tensor(data, es_idx, tasks, z_mean, z_sd)
    best, best_state, best_epoch, bad, history = np.inf, None, 0, 0, []
    rng = np.random.default_rng(seed)
    epoch = 0
    for epoch in range(1, max_epochs + 1):
        network.train()
        perm = fit_idx[rng.permutation(len(fit_idx))]
        train_losses = []
        for start_row in range(0, len(perm), cfg["batch_size"]):
            rows = perm[start_row : start_row + cfg["batch_size"]]
            if len(rows) < 2:  # batch norm needs at least two rows
                continue
            out = network(to_batch(data, rows, codes))
            losses = task_losses(out, _targets_tensor(data, rows, tasks, z_mean, z_sd), weights)
            loss = combine(losses, network, name, cfg)
            opt.zero_grad()
            loss.backward()
            opt.step()
            train_losses.append(float(sum(v.item() for v in losses.values())))
        network.eval()
        with torch.no_grad():
            es_losses = task_losses(network(es_batch), es_targets, weights)
        es_total = float(sum(v.item() for v in es_losses.values()))
        record = {"epoch": epoch, "train_loss": float(np.mean(train_losses)), "es_loss": es_total}
        record.update({f"es_loss_{t}": float(v.item()) for t, v in es_losses.items()})
        if name == "mtl":
            record.update({f"log_var_{t}": float(network.log_vars[t].item()) for t in tasks})
        history.append(record)
        if es_total < best - 1e-6:
            best, best_state, best_epoch, bad = (
                es_total,
                copy.deepcopy(network.state_dict()),
                epoch,
                0,
            )
        else:
            bad += 1
            if bad >= cfg["patience"]:
                break
    if best_state is not None:
        network.load_state_dict(best_state)
    network.eval()
    return Fitted(
        name=name,
        cfg=cfg,
        tasks=tasks,
        network=network,
        z_mean=z_mean,
        z_sd=z_sd,
        best_epoch=best_epoch,
        epochs_run=epoch,
        seconds=time.perf_counter() - start,
        n_params=count_parameters(network) + (count_parameters(autoencoder) if autoencoder else 0),
        history=history,
        autoencoder=autoencoder,
        ae_history=ae_history,
    )


def predict(model: Fitted, data: ModelData) -> dict[str, np.ndarray]:
    """Z-score on its original scale and class probabilities for every task."""
    codes = None
    with torch.no_grad():
        if model.autoencoder is not None:
            codes = model.autoencoder.encode(torch.from_numpy(data.x)).numpy()
        out = model.network(to_batch(data, None, codes))
    result = {}
    for task, value in out.items():
        if task == "zscore":
            result[task] = value.numpy() * model.z_sd + model.z_mean
        else:
            result[task] = torch.softmax(value, dim=1).numpy()
    return result


def reconstruction_mse(model: Fitted, data: ModelData) -> float:
    """Autoencoder reconstruction error (MSE) on the given rows."""
    if model.autoencoder is None:
        raise ValueError("Model has no autoencoder")
    with torch.no_grad():
        x = torch.from_numpy(data.x)
        return float(nn.functional.mse_loss(model.autoencoder(x), x).item())
