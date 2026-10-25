from aegis.collector import Sample


def config(capacity_rps=24, startup_time_seconds=15):
    return {
        "capacity_rps": capacity_rps,
        "startup_time_seconds": startup_time_seconds,
        "sampling": {"interval_seconds": 5, "projection_window_seconds": 30, "metric_lag_seconds": 20},
        "sigma": {"initial_rps": 2, "min_rps": 1.0, "window_seconds": 300, "min_errors": 6},
        "risk_thresholds": {"scale_up": 0.70, "scale_down": 0.30, "scale_down_sustained_seconds": 60},
        "kubernetes": {"min_replicas": 1, "max_replicas": 3},
    }


# Feeds a traffic trace (one value every 5 s) and returns the last projection.
def feed(calculator, values, start=1000.0, step=5.0):
    result = None
    for index, rps in enumerate(values):
        result = calculator.update(Sample(start + index * step, rps, 0.1, 1))
    return result
