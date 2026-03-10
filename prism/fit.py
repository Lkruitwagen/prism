"""Generic JAX-based power curve fitting with quantile loss."""

from collections.abc import Callable

import jax
import jax.numpy as jnp
import numpy as np
from scipy.optimize import OptimizeResult, minimize


def quantile_loss(predictions: jnp.ndarray, targets: jnp.ndarray, tau: float = 0.9) -> jnp.ndarray:
    """Asymmetric quantile (pinball) loss.

    With tau > 0.5 the fitted curve follows the upper envelope of observations,
    which naturally handles periods of curtailment (observed < uncurtailed output).

    Args:
        predictions: Model-predicted values.
        targets: Observed values.
        tau: Quantile in (0, 1). Default 0.5 is the median (MAE), fitting through
            the bulk of the data. Use tau > 0.5 only if you specifically want
            the upper envelope (e.g. for explicit curtailment modelling).

    Returns:
        Scalar mean quantile loss.
    """
    errors = targets - predictions
    return jnp.mean(jnp.where(errors >= 0, tau * errors, (tau - 1.0) * errors))


def fit(
    power_fn: Callable[[jnp.ndarray, jnp.ndarray], jnp.ndarray],
    init_params: np.ndarray,
    met_values: np.ndarray,
    observed: np.ndarray,
    tau: float = 0.5,
    method: str = "L-BFGS-B",
) -> OptimizeResult:
    """Fit a power curve using JAX autograd + scipy.optimize.minimize.

    The loss is an asymmetric quantile loss so that curtailed periods (where
    observed generation is forced below the physical curve) do not bias the fit.

    Args:
        power_fn: Callable (params, met_values) -> predicted_mw. Must be JAX-compatible.
        init_params: Initial parameter vector (numpy array, typically log-transformed).
        met_values: Meteorological input (numpy 1-D array: wind speed or solar radiation).
        observed: Observed generation (numpy 1-D array, MW). Must match met_values length.
        tau: Quantile for asymmetric loss (default 0.9).
        method: scipy minimisation method (default 'L-BFGS-B').

    Returns:
        scipy OptimizeResult; fitted parameters are in result.x.
    """
    met_jax = jnp.array(met_values, dtype=jnp.float32)
    obs_jax = jnp.array(observed, dtype=jnp.float32)

    @jax.jit
    def loss_fn(params: jnp.ndarray) -> jnp.ndarray:
        pred = power_fn(params, met_jax)
        return quantile_loss(pred, obs_jax, tau)

    val_and_grad = jax.jit(jax.value_and_grad(loss_fn))

    def objective(params: np.ndarray) -> tuple[float, np.ndarray]:
        params_jax = jnp.array(params, dtype=jnp.float32)
        val, grad = val_and_grad(params_jax)
        return float(val), np.array(grad, dtype=np.float64)

    return minimize(objective, init_params.astype(np.float64), jac=True, method=method)


def predict(
    power_fn: Callable[[jnp.ndarray, jnp.ndarray], jnp.ndarray],
    params: np.ndarray,
    met_values: np.ndarray,
) -> np.ndarray:
    """Run a fitted power curve over met data and return numpy predictions (MW)."""
    return np.array(
        power_fn(jnp.array(params, dtype=jnp.float32), jnp.array(met_values, dtype=jnp.float32))
    )
