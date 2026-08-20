"""
tests/test_anomaly.py — Unit tests for EWMA anomaly detector.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from monitoring.anomaly import EWMADetector, AnomalyEngine

class TestEWMADetector:
    def test_warmup_no_alerts(self):
        det = EWMADetector("test", warmup=5)
        for i in range(5):
            assert det.feed(100.0) is False    # no alert during warmup

    def test_normal_traffic_no_alert(self):
        det = EWMADetector("test", alpha=0.3, threshold=3.0, warmup=5)
        for _ in range(50):
            det.feed(100.0)                    # stable traffic
        assert det.feed(102.0) is False        # tiny change, no alert

    def test_spike_triggers_alert(self):
        """
        EWMA detects anomaly when traffic deviates significantly from baseline.
        We feed varied traffic (gaussian-like variation) so sigma builds up,
        then inject a 10x spike which exceeds the 3-sigma threshold.
        """
        import random
        random.seed(42)
        det = EWMADetector("test", alpha=0.3, threshold=3.0, warmup=5)
        # Feed varied baseline — this lets sigma accumulate
        for _ in range(50):
            det.feed(100.0 + random.gauss(0, 5))   # mean=100, std=5
        # Now inject a spike 20x above baseline — far outside 3-sigma
        assert det.feed(2000.0) is True

    def test_stats_returns_dict(self):
        det = EWMADetector("pkt_rate")
        for i in range(10):
            det.feed(float(i))
        s = det.stats()
        assert "ewma" in s and "sigma" in s and "count" in s

    def test_engine_manages_multiple_metrics(self):
        eng = AnomalyEngine("ctrl_01")
        eng.check("pkt_rate", 100.0)
        eng.check("flow_rate", 5.0)
        stats = eng.all_stats()
        assert "pkt_rate"  in stats
        assert "flow_rate" in stats
