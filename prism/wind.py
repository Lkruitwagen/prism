"""Wind power curve models."""

import jax.nn
import jax.numpy as jnp
import numpy as np


def wind_power(params: jnp.ndarray, wind_speed: jnp.ndarray) -> jnp.ndarray:
    """Physical wind power curve: cut-in → power-law rise → rated plateau → cut-out.

    Parameters are log-transformed so they are unconstrained during optimisation.

    Args:
        params: Array of 5 log-transformed parameters:
            params[0]: log(capacity) — Rated capacity (MW)
            params[1]: log(v_cutin)  — Cut-in wind speed (m/s)
            params[2]: log(v_rated)  — Rated wind speed (m/s), start of plateau
            params[3]: log(k)        — Shape exponent for the rising portion (typically 2–3)
            params[4]: log(v_cutout) — Cut-out wind speed (m/s)
        wind_speed: Wind speed array (m/s).

    Returns:
        Predicted power output (MW).
    """
    capacity = jnp.exp(params[0])
    v_cutin = jnp.exp(params[1])
    v_rated = jnp.exp(params[2])
    k = jnp.exp(params[3])
    v_cutout = jnp.exp(params[4])

    # Normalised position in the rising portion [cutin, rated].
    # Protect denominator so it can't collapse to zero.
    dv = jnp.maximum(v_rated - v_cutin, 0.1)
    norm = (wind_speed - v_cutin) / dv

    # Clip to [eps, 1]: eps avoids NaN gradients of x^k at x=0 when k < 1.
    # norm_safe == 1.0 above v_rated → plateau; near eps below v_cutin → ~0.
    norm_safe = jnp.clip(norm, 1e-4, 1.0)

    # Power-law rise → flat plateau
    rising = norm_safe**k

    # Smooth masks via jax.nn.sigmoid (numerically stable, no NaN gradients)
    cutin_mask = jax.nn.sigmoid(20.0 * (wind_speed - v_cutin))  # ~0 below, ~1 above cut-in
    cutout_mask = jax.nn.sigmoid(-10.0 * (wind_speed - v_cutout))  # ~1 below, ~0 above cut-out

    return capacity * rising * cutin_mask * cutout_mask


def wind_power_weibull(params: jnp.ndarray, wind_speed: jnp.ndarray) -> jnp.ndarray:
    """Weibull CDF wind power curve (original model, kept for comparison).

    Note: lacks an explicit rated-speed plateau; tends to underfit at high wind speeds.

    Args:
        params: Array of 4 log-transformed parameters:
            params[0]: log(scale)    — Weibull scale parameter λ (m/s)
            params[1]: log(shape)    — Weibull shape parameter k (dimensionless)
            params[2]: log(capacity) — Rated capacity (MW)
            params[3]: log(cutout)   — Cut-out wind speed (m/s)
        wind_speed: Wind speed array (m/s).
    """
    scale = jnp.exp(params[0])
    shape = jnp.exp(params[1])
    capacity = jnp.exp(params[2])
    cutout = jnp.exp(params[3])

    weibull_cdf = 1.0 - jnp.exp(-((wind_speed / scale) ** shape))
    cutout_mask = jax.nn.sigmoid(-10.0 * (wind_speed - cutout))
    return capacity * weibull_cdf * cutout_mask


def default_params(capacity_mw: float = 100.0) -> np.ndarray:
    """Default initial log-params for wind power curve fitting.

    Args:
        capacity_mw: Rough estimate of rated capacity (MW) for initialisation.
    """
    return np.array(
        [
            np.log(capacity_mw),  # rated capacity
            np.log(3.5),  # cut-in ~ 3.5 m/s
            np.log(13.0),  # rated speed ~ 13 m/s
            np.log(2.0),  # shape exponent ~ 2 (quadratic rise)
            np.log(25.0),  # cut-out ~ 25 m/s
        ]
    )


def param_names() -> list[str]:
    """Human-readable names for wind power curve parameters."""
    return ["capacity (MW)", "v_cutin (m/s)", "v_rated (m/s)", "k (shape)", "v_cutout (m/s)"]
