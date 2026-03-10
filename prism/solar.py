"""Solar power curve — linear efficiency model."""

import jax.numpy as jnp
import numpy as np


def solar_power(params: jnp.ndarray, solar_radiation: jnp.ndarray) -> jnp.ndarray:
    """Linear solar power curve: P = scale × G.

    Parameters are log-transformed so they are unconstrained during optimisation.

    Args:
        params: Array of 1 log-transformed parameter:
            params[0]: log(scale) — MW per (W/m²)
        solar_radiation: Surface solar radiation downwards (W/m²).

    Returns:
        Predicted power output (MW).
    """
    scale = jnp.exp(params[0])
    return scale * jnp.maximum(solar_radiation, 0.0)


def default_params(capacity_mw: float = 10.0) -> np.ndarray:
    """Default initial log-params for solar power curve fitting.

    Assumes peak irradiance ~1000 W/m² → capacity_mw output,
    so initial scale ≈ capacity_mw / 1000.

    Args:
        capacity_mw: Rough estimate of rated capacity (MW) for initialisation.
    """
    scale_init = capacity_mw / 1000.0
    return np.array([np.log(scale_init)])


def param_names() -> list[str]:
    """Human-readable names for solar power curve parameters."""
    return ["scale (MW per W/m²)"]
