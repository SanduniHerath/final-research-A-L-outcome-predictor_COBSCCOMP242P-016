"""The eight neural-network architectures (Phase 6). No ensembles of any kind.

Every network maps a batch to ``{task: output}``: a single value for ``zscore`` and
logits for the three classification tasks. Passing a subset of tasks builds the
single-task version of the same architecture (needed for the negative-transfer check).
"""

from __future__ import annotations

from typing import Any

import torch
from pytorch_tabnet import tab_network
from torch import nn

TASK_DIMS = {"zscore": 1, "zscore_band": 3, "university_group": 5, "degree_category": 7}

Batch = dict[str, torch.Tensor]
Outputs = dict[str, torch.Tensor]


def mlp_layers(
    in_dim: int, layers: int, units: int, dropout: float = 0.0, batchnorm: bool = False
) -> tuple[nn.Sequential, int]:
    """Stack of Linear -> (BatchNorm) -> ReLU -> (Dropout) blocks; returns it and its width."""
    blocks: list[nn.Module] = []
    width = in_dim
    for _ in range(layers):
        blocks.append(nn.Linear(width, units))
        if batchnorm:
            blocks.append(nn.BatchNorm1d(units))
        blocks.append(nn.ReLU())
        if dropout > 0:
            blocks.append(nn.Dropout(dropout))
        width = units
    return nn.Sequential(*blocks), width


def heads(width: int, tasks: list[str]) -> nn.ModuleDict:
    """One linear output layer per task."""
    return nn.ModuleDict({t: nn.Linear(width, TASK_DIMS[t]) for t in tasks})


def _apply_heads(h: torch.Tensor, head: nn.ModuleDict) -> Outputs:
    out = {t: layer(h) for t, layer in head.items()}
    if "zscore" in out:
        out["zscore"] = out["zscore"].squeeze(-1)
    return out


class MLPNet(nn.Module):
    """Plain MLP (mlp) or regularised deep network with batch norm and dropout (reg_dnn)."""

    def __init__(
        self,
        in_dim: int,
        tasks: list[str],
        layers: int,
        units: int,
        dropout: float = 0.0,
        batchnorm: bool = False,
    ) -> None:
        super().__init__()
        self.body, width = mlp_layers(in_dim, layers, units, dropout, batchnorm)
        self.head = heads(width, tasks)

    def forward(self, batch: Batch) -> Outputs:  # noqa: D102
        return _apply_heads(self.body(batch["x"]), self.head)


class WideDeepNet(nn.Module):
    """Wide (linear on inputs + hand-made crosses) plus deep (MLP) parts; outputs are added."""

    def __init__(
        self,
        in_dim: int,
        wide_dim: int,
        tasks: list[str],
        layers: int,
        units: int,
        dropout: float,
        use_wide: bool = True,
        use_deep: bool = True,
    ) -> None:
        super().__init__()
        if not (use_wide or use_deep):
            raise ValueError("Wide & Deep needs at least one part")
        self.use_wide, self.use_deep = use_wide, use_deep
        if use_wide:
            self.wide = heads(wide_dim, tasks)
        if use_deep:
            self.body, width = mlp_layers(in_dim, layers, units, dropout)
            self.deep = heads(width, tasks)
        self.tasks = tasks

    def forward(self, batch: Batch) -> Outputs:  # noqa: D102
        out: Outputs = {}
        if self.use_wide:
            out = _apply_heads(batch["wide"], self.wide)
        if self.use_deep:
            deep = _apply_heads(self.body(batch["x"]), self.deep)
            out = {t: out[t] + deep[t] for t in self.tasks} if out else deep
        return out


class TabNetNet(nn.Module):
    """TabNet encoder with one output mapping per task (pytorch-tabnet network)."""

    def __init__(
        self,
        in_dim: int,
        tasks: list[str],
        n_d: int,
        n_steps: int,
        gamma: float,
        virtual_batch_size: int,
    ) -> None:
        super().__init__()
        self.tasks = tasks
        self.net = tab_network.TabNet(
            input_dim=in_dim,
            output_dim=[TASK_DIMS[t] for t in tasks],
            n_d=n_d,
            n_a=n_d,
            n_steps=n_steps,
            gamma=gamma,
            virtual_batch_size=virtual_batch_size,
            group_attention_matrix=torch.eye(in_dim),
        )
        self.last_sparsity_loss = torch.tensor(0.0)

    def forward(self, batch: Batch) -> Outputs:  # noqa: D102
        outputs, sparsity = self.net(batch["x"])
        self.last_sparsity_loss = sparsity
        if not isinstance(outputs, list):
            outputs = [outputs]
        out = dict(zip(self.tasks, outputs, strict=True))
        if "zscore" in out:
            out["zscore"] = out["zscore"].squeeze(-1)
        return out

    def masks(self, x: torch.Tensor) -> tuple[torch.Tensor, dict[int, torch.Tensor]]:
        """Aggregated attention importance per row, and the mask of every step."""
        return self.net.forward_masks(x)


class MTLNet(nn.Module):
    """Shared trunk, one tower per task, and learned loss weights (log variances)."""

    def __init__(
        self,
        in_dim: int,
        tasks: list[str],
        shared_layers: int,
        units: int,
        tower_units: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.body, width = mlp_layers(in_dim, shared_layers, units, dropout)
        self.towers = nn.ModuleDict(
            {
                t: nn.Sequential(
                    nn.Linear(width, tower_units), nn.ReLU(), nn.Linear(tower_units, TASK_DIMS[t])
                )
                for t in tasks
            }
        )
        self.log_vars = nn.ParameterDict({t: nn.Parameter(torch.zeros(1)) for t in tasks})

    def forward(self, batch: Batch) -> Outputs:  # noqa: D102
        return _apply_heads(self.body(batch["x"]), self.towers)


class EntityMLPNet(nn.Module):
    """MLP whose district input is a learned embedding instead of one-hot columns."""

    def __init__(
        self,
        in_dim: int,
        n_districts: int,
        tasks: list[str],
        layers: int,
        units: int,
        emb_dim: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.embedding = nn.Embedding(n_districts + 1, emb_dim)  # index 0 = unknown district
        self.body, width = mlp_layers(in_dim + emb_dim, layers, units, dropout)
        self.head = heads(width, tasks)

    def forward(self, batch: Batch) -> Outputs:  # noqa: D102
        x = torch.cat([batch["x"], self.embedding(batch["district"])], dim=1)
        return _apply_heads(self.body(x), self.head)


class AutoEncoder(nn.Module):
    """Symmetric autoencoder; ``encode`` gives the compressed representation."""

    def __init__(self, in_dim: int, hidden: int, bottleneck: int) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.ReLU(), nn.Linear(hidden, bottleneck)
        )
        self.decoder = nn.Sequential(
            nn.Linear(bottleneck, hidden), nn.ReLU(), nn.Linear(hidden, in_dim)
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:  # noqa: D102
        return self.encoder(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # noqa: D102
        return self.decoder(self.encoder(x))


class ResidualBlock(nn.Module):
    """BatchNorm -> Linear -> ReLU -> Dropout -> Linear, added to the input."""

    def __init__(self, units: int, dropout: float) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.BatchNorm1d(units),
            nn.Linear(units, units),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(units, units),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # noqa: D102
        return x + self.block(x)


class ResNetNet(nn.Module):
    """ResNet-style tabular network (Gorishniy et al., 2021)."""

    def __init__(
        self, in_dim: int, tasks: list[str], blocks: int, units: int, dropout: float
    ) -> None:
        super().__init__()
        self.stem = nn.Linear(in_dim, units)
        self.blocks = nn.Sequential(*[ResidualBlock(units, dropout) for _ in range(blocks)])
        self.out_norm = nn.Sequential(nn.BatchNorm1d(units), nn.ReLU())
        self.head = heads(units, tasks)

    def forward(self, batch: Batch) -> Outputs:  # noqa: D102
        return _apply_heads(self.out_norm(self.blocks(self.stem(batch["x"]))), self.head)


def build_network(
    name: str, cfg: dict[str, Any], dims: dict[str, int], tasks: list[str]
) -> nn.Module:
    """Create the network ``name`` with hyperparameters ``cfg``.

    Args:
        name: Model key from ``configs/models.yaml``.
        cfg: Hyperparameters of this configuration.
        dims: ``in_dim`` and, where needed, ``wide_dim`` and ``n_districts``.
        tasks: Tasks (heads) to build.
    """
    d = dims["in_dim"]
    if name == "mlp":
        return MLPNet(d, tasks, cfg["layers"], cfg["units"])
    if name == "mlp_dropout":  # comparison network: MLP with dropout, no batch norm
        return MLPNet(d, tasks, cfg["layers"], cfg["units"], cfg.get("dropout", 0.0))
    if name == "reg_dnn":
        return MLPNet(d, tasks, cfg["layers"], cfg["units"], cfg["dropout"], batchnorm=True)
    if name == "wide_deep":
        return WideDeepNet(
            d,
            dims["wide_dim"],
            tasks,
            cfg["layers"],
            cfg["units"],
            cfg["dropout"],
            cfg.get("use_wide", True),
            cfg.get("use_deep", True),
        )
    if name == "tabnet":
        return TabNetNet(
            d, tasks, cfg["n_d"], cfg["n_steps"], cfg["gamma"], cfg["virtual_batch_size"]
        )
    if name == "mtl":
        return MTLNet(
            d, tasks, cfg["shared_layers"], cfg["units"], cfg["tower_units"], cfg["dropout"]
        )
    if name == "entity_mlp":
        return EntityMLPNet(
            d,
            dims["n_districts"],
            tasks,
            cfg["layers"],
            cfg["units"],
            cfg["emb_dim"],
            cfg["dropout"],
        )
    if name == "ae_mlp":
        return MLPNet(cfg["bottleneck"], tasks, cfg["layers"], cfg["units"], cfg["dropout"])
    if name == "resnet":
        return ResNetNet(d, tasks, cfg["blocks"], cfg["units"], cfg["dropout"])
    raise ValueError(f"Unknown model {name!r}")


def count_parameters(module: nn.Module) -> int:
    """Number of trainable parameters."""
    return sum(p.numel() for p in module.parameters() if p.requires_grad)
