"""
monitoring/anomaly.py
Statistical anomaly detection using Exponentially Weighted Moving Average (EWMA).

ALGORITHM:
  For a stream of values x[t]:
    ewma[t]  = alpha * x[t] + (1-alpha) * ewma[t-1]
    sigma[t] = sqrt(alpha*(x[t]-ewma[t])^2 + (1-alpha)*sigma[t-1]^2)
    anomaly  = |x[t] - ewma[t]| > threshold * sigma[t]

This detects sudden spikes (floods) and gradual drift (slow poisoning) both.
Threshold=3.0 → 3-sigma rule (normal distribution: 99.7% of normal traffic passes).
"""
import math, time
from collections import deque
from shared.logger import get_logger

log = get_logger("monitoring.anomaly")

class EWMADetector:
    """
    Exponentially Weighted Moving Average anomaly detector.
    One instance per metric per controller (e.g. packet rate, flow rate).
    """
    def __init__(self, name: str, alpha: float = 0.1, threshold: float = 3.0,
                 warmup: int = 10):
        self.name      = name
        self.alpha     = alpha        # smoothing factor (0.1 = slow, 0.5 = fast)
        self.threshold = threshold    # sigma multiplier (3.0 = 3-sigma rule)
        self.warmup    = warmup       # samples before detection starts
        self._ewma     = None
        self._sigma    = None
        self._count    = 0
        self._history  = deque(maxlen=500)

    def feed(self, value: float) -> bool:
        """
        Feed a new sample. Returns True if anomalous, False if normal.
        """
        self._count += 1
        self._history.append({"ts": time.time(), "v": value})

        if self._ewma is None:
            self._ewma  = value
            self._sigma = 0.0
            return False

        # Save pre-update values for anomaly scoring (before the spike contaminates them)
        prev_ewma  = self._ewma
        prev_sigma = self._sigma

        # Update EWMA mean
        self._ewma  = self.alpha * value + (1 - self.alpha) * self._ewma

        # Update EWMA variance (for next round) using deviation from prior mean
        diff        = value - prev_ewma
        var         = self.alpha * diff**2 + (1 - self.alpha) * (prev_sigma**2)
        self._sigma = math.sqrt(var)

        # Not enough warmup yet → skip detection
        if self._count < self.warmup:
            return False

        # Score anomaly using PRE-SPIKE sigma (not the spike-inflated one)
        # Floor: max(prior_sigma, 1% of prior_mean + 1.0 absolute) to avoid div/0
        eff_sigma = max(prev_sigma, prev_ewma * 0.01 + 1.0)
        z_score   = abs(value - prev_ewma) / eff_sigma
        if z_score > self.threshold:
            log.warning(f"[ANOMALY] {self.name}: value={value:.1f} "
                        f"ewma={self._ewma:.1f} sigma={self._sigma:.1f} z={z_score:.2f}")
            return True
        return False

    def stats(self) -> dict:
        return {
            "name":   self.name,
            "ewma":   round(self._ewma or 0, 2),
            "sigma":  round(self._sigma or 0, 2),
            "count":  self._count,
            "warmup": self._count >= self.warmup,
        }


class AnomalyEngine:
    """
    Manages multiple EWMA detectors — one per metric.
    Call check(metric_name, value) from the integrity agent.
    """
    def __init__(self, cid: str):
        self.cid      = cid
        self._detectors = {}

    def check(self, metric: str, value: float) -> bool:
        """Returns True if anomalous."""
        if metric not in self._detectors:
            self._detectors[metric] = EWMADetector(f"{self.cid}:{metric}")
        return self._detectors[metric].feed(value)

    def all_stats(self) -> dict:
        return {m: d.stats() for m, d in self._detectors.items()}
