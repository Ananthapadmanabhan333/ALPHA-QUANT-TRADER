import random


def compute_exponential_backoff_jitter(
    attempt: int,
    initial_backoff: float = 1.0,
    max_backoff: float = 60.0,
    backoff_factor: float = 2.0,
) -> float:
    """
    Computes exponential backoff with full jitter to avoid thundering herds
    during exchange disconnections.
    """
    if attempt <= 0:
        return random.uniform(0, initial_backoff)

    calculated_backoff = min(max_backoff, initial_backoff * (backoff_factor ** attempt))
    # Full jitter: random sleep between 0 and calculated_backoff
    return random.uniform(0.1, calculated_backoff)
