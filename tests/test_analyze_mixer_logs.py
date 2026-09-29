from pathlib import Path
import tempfile
import unittest

from tools.analyze_mixer_logs import RoundMetric, included_rounds, parse_log, per_node_averages


class MixerLogAnalysisTests(unittest.TestCase):
    def test_excludes_startup_round_from_every_average(self):
        rounds = [
            RoundMetric(100, 1, 1800.0, 10000.0, 0.20, 50.0, "test:printed"),
            RoundMetric(100, 2, 800.0, 300.0, 0.48, 100.0, "test:printed"),
        ]
        steady = included_rounds(rounds, include_first_round=False)
        self.assertEqual([metric.round for metric in steady], [2])
        average = per_node_averages(steady)[0]
        self.assertEqual(average["rounds"], 1)
        self.assertEqual(average["avg_latency_ms"], 800.0)
        self.assertEqual(average["avg_radio_on_ms"], 300.0)
        self.assertEqual(average["avg_goodput_kBps"], 0.48)
        self.assertEqual(average["avg_reliability_pct"], 100.0)
        self.assertEqual(included_rounds(rounds, include_first_round=True), rounds)

    def test_derives_metrics_from_pre_metric_log(self):
        text = """DCUBE phy=IEEE802154 channel=26 tx_dbm=8 payload=8 slot_us=5000 slots=360 gap_ms=1000
GPI_TICK_US_TO_HYBRID2(1) = 16
MX_NUM_NODES              = 48
MX_PAYLOAD_SIZE           = 8
MX_SLOT_LENGTH            = 80000
2026-01-01 00:00:00|statistics:
2026-01-01 00:00:00|radio_on_time: 250000us
2026-01-01 00:00:00|# ID:100 round=1 rank=48 dec=48 !dec=0 weak=0 wrong=0 stale=0 synced=1
2026-01-01 00:00:00|# ID:100 rank_up_slot=[0;3;240;]
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "log_100.txt"
            log.write_text(text)
            rounds = parse_log(log, root)
        self.assertEqual(len(rounds), 1)
        metric = rounds[0]
        self.assertEqual(metric.source, "log_100.txt:derived")
        self.assertEqual(metric.latency_ms, 1200.0)
        self.assertEqual(metric.radio_on_ms, 250.0)
        self.assertEqual(metric.reliability_pct, 100.0)
        self.assertEqual(metric.goodput_kBps, 0.32)

    def test_uses_printed_metrics(self):
        text = """2026-01-01 00:00:00|statistics:
2026-01-01 00:00:00|radio_on_time: 999999us
2026-01-01 00:00:00|# ID:200 round=9 rank=48 dec=47 !dec=1 weak=0 wrong=0 stale=0 synced=1 latency_ms=1000.500 radio_on_ms=200.250 goodput_kBps=0.384 reliability_pct=97.92
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "log_200.txt"
            log.write_text(text)
            rounds = parse_log(log, root)
        self.assertEqual(len(rounds), 1)
        metric = rounds[0]
        self.assertEqual(metric.source, "log_200.txt:printed")
        self.assertEqual(metric.latency_ms, 1000.5)
        self.assertEqual(metric.radio_on_ms, 200.25)
        self.assertEqual(metric.goodput_kBps, 0.384)
        self.assertEqual(metric.reliability_pct, 97.92)
        average = per_node_averages(rounds)[0]
        self.assertEqual(average["metric_source"], "printed")


if __name__ == "__main__":
    unittest.main()
