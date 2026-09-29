#!/usr/bin/env python3
"""Summarize and plot per-node Mixer metrics from a D-Cube log directory.

The script accepts both current metric-enabled firmware logs and older Mixer
logs. Current logs contain latency_ms, radio_on_ms, goodput_kBps, and
reliability_pct in every '# ID:' result line. For older logs the script derives
the equivalent values from rank_up_slot, radio_on_time, payload size, and the
number of decoded messages. Round 1 is excluded from every average by default
because its startup scan can dominate radio-on time.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean


RESULT_LINE = re.compile(r"# ID:(?P<node>\d+)\s+round=(?P<round>\d+)(?P<rest>.*)")
KEY_VALUE = re.compile(r"(?P<key>[A-Za-z_!]+)=(?P<value>[^\s\[\]]+)")
RANK_UP_SLOTS = re.compile(r"# ID:(?P<node>\d+)\s+rank_up_slot=\[(?P<slots>[^\]]*)\]")
STAT_VALUE = re.compile(r"\|(?P<key>[A-Za-z_]+):\s*(?P<value>\d+)(?P<unit>us)?\s*$")
CONFIG_VALUE = re.compile(r"\|(?P<key>MX_(?:NUM_NODES|PAYLOAD_SIZE|SLOT_LENGTH))\s+=\s*(?P<value>\d+)\s*$")
HYBRID_TICKS_PER_US = re.compile(r"\|GPI_TICK_US_TO_HYBRID2\(1\)\s+=\s*(?P<value>\d+)\s*$")
DCUBE_CONFIG = re.compile(
    r"DCUBE phy=.*?payload=(?P<payload>\d+)\s+slot_us=(?P<slot_us>\d+)"
)


@dataclass
class RoundMetric:
    node: int
    round: int
    latency_ms: float | None
    radio_on_ms: float | None
    goodput_kBps: float | None
    reliability_pct: float | None
    source: str


def number(value: str) -> float | None:
    """Read a numeric metric, treating NA and malformed values as missing."""
    try:
        return float(value)
    except ValueError:
        return None


def parse_config(lines: list[str]) -> tuple[int, int, float]:
    """Return node count, payload bytes, and slot duration in milliseconds."""
    nodes, payload, slot_ms = 48, 8, 5.0
    slot_length_ticks: int | None = None
    hybrid_ticks_per_us: int | None = None
    for line in lines:
        dcube = DCUBE_CONFIG.search(line)
        if dcube:
            payload = int(dcube["payload"])
            slot_ms = int(dcube["slot_us"]) / 1_000
        tick_match = HYBRID_TICKS_PER_US.search(line)
        if tick_match:
            hybrid_ticks_per_us = int(tick_match["value"])
        match = CONFIG_VALUE.search(line)
        if not match:
            continue
        value = int(match["value"])
        if match["key"] == "MX_NUM_NODES":
            nodes = value
        elif match["key"] == "MX_PAYLOAD_SIZE":
            payload = value
        elif match["key"] == "MX_SLOT_LENGTH":
            slot_length_ticks = value
    if slot_length_ticks is not None and hybrid_ticks_per_us:
        slot_ms = slot_length_ticks / hybrid_ticks_per_us / 1_000
    return nodes, payload, slot_ms


def parse_log(log_file: Path, root: Path) -> list[RoundMetric]:
    """Parse all complete result records from one node log."""
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    node_count, payload_bytes, slot_ms = parse_config(lines)
    statistics: dict[str, int] | None = None
    records: list[RoundMetric] = []
    source_name = str(log_file.relative_to(root))

    for index, line in enumerate(lines):
        if "|statistics:" in line:
            statistics = {}
            continue
        if statistics is not None:
            stat = STAT_VALUE.search(line)
            if stat:
                statistics[stat["key"]] = int(stat["value"])
                continue

        result = RESULT_LINE.search(line)
        if not result:
            continue
        fields = {match["key"]: match["value"] for match in KEY_VALUE.finditer(result["rest"])}
        decoded = number(fields.get("dec", ""))
        direct_latency = number(fields.get("latency_ms", ""))
        direct_radio = number(fields.get("radio_on_ms", ""))
        direct_goodput = number(fields.get("goodput_kBps", ""))
        direct_reliability = number(fields.get("reliability_pct", ""))
        derived = any(value is None for value in (
            direct_latency, direct_radio, direct_goodput, direct_reliability
        ))

        last_rank_slot: int | None = None
        if derived and index + 1 < len(lines):
            rank_slots = RANK_UP_SLOTS.search(lines[index + 1])
            if rank_slots:
                slots = [int(value) for value in rank_slots["slots"].split(";") if value]
                last_rank_slot = max(slots) if slots else None

        latency_ms = direct_latency
        if latency_ms is None and last_rank_slot is not None:
            latency_ms = last_rank_slot * slot_ms
        radio_on_ms = direct_radio
        if radio_on_ms is None and statistics is not None:
            radio_on_us = statistics.get("radio_on_time")
            radio_on_ms = radio_on_us / 1_000 if radio_on_us is not None else None
        reliability_pct = direct_reliability
        if reliability_pct is None and decoded is not None:
            reliability_pct = decoded * 100 / node_count
        goodput_kBps = direct_goodput
        if goodput_kBps is None and latency_ms:
            # Decimal kB/s: payload bytes / milliseconds has this same value.
            goodput_kBps = payload_bytes * node_count / latency_ms

        source = "printed" if not derived else "derived"
        records.append(RoundMetric(
            node=int(result["node"]), round=int(result["round"]),
            latency_ms=latency_ms, radio_on_ms=radio_on_ms,
            goodput_kBps=goodput_kBps, reliability_pct=reliability_pct,
            source=source_name + ":" + source,
        ))
        statistics = None
    return records


def mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return fmean(present) if present else None


def included_rounds(rounds: list[RoundMetric], include_first_round: bool) -> list[RoundMetric]:
    return [metric for metric in rounds if include_first_round or metric.round != 1]


def per_node_averages(rounds: list[RoundMetric]) -> list[dict[str, object]]:
    by_node: dict[int, list[RoundMetric]] = {}
    for metric in rounds:
        by_node.setdefault(metric.node, []).append(metric)
    output = []
    for node, node_rounds in sorted(by_node.items()):
        output.append({
            "node": node,
            "rounds": len(node_rounds),
            "avg_latency_ms": mean([item.latency_ms for item in node_rounds]),
            "avg_radio_on_ms": mean([item.radio_on_ms for item in node_rounds]),
            "avg_goodput_kBps": mean([item.goodput_kBps for item in node_rounds]),
            "avg_reliability_pct": mean([item.reliability_pct for item in node_rounds]),
            "metric_source": "printed" if all(item.source.endswith(":printed") for item in node_rounds) else "derived",
        })
    return output


METRICS = (
    ("avg_latency_ms", "Latency", "ms", "#2878b5"),
    ("avg_radio_on_ms", "Radio-on time", "ms", "#4c9f70"),
    ("avg_goodput_kBps", "Goodput", "kB/s", "#d99028"),
    ("avg_reliability_pct", "Reliability", "%", "#9b59b6"),
)


def write_csv(records: list[dict[str, object]], destination: Path) -> None:
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def make_plots(records: list[dict[str, object]], output_dir: Path,
               include_first_round: bool) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Plotting requires matplotlib. Install it with: pip install matplotlib") from exc

    nodes = [int(record["node"]) for record in records]
    round_label = "all rounds" if include_first_round else "rounds 2+"
    figure, axes = plt.subplots(2, 2, figsize=(17, 10), constrained_layout=True)
    for axis, (field, title, unit, color) in zip(axes.flat, METRICS):
        values = [float(record[field]) if record[field] is not None else float("nan") for record in records]
        fleet_mean = mean(values)
        axis.bar(range(len(nodes)), values, color=color)
        axis.set_title(f"Per-node average {title}")
        axis.set_ylabel(unit)
        axis.set_xticks(range(len(nodes)))
        axis.set_xticklabels(nodes, rotation=90, fontsize=7)
        axis.grid(axis="y", alpha=0.25)
        if fleet_mean is not None:
            axis.axhline(fleet_mean, color="#c0392b", linestyle="--", linewidth=1.3,
                         label=f"fleet average: {fleet_mean:.3f} {unit}")
            axis.legend(fontsize=8)
        if field == "avg_reliability_pct":
            axis.set_ylim(0, 102)
    figure.suptitle(f"Mixer D-Cube per-node averages ({round_label})", fontsize=16)
    figure.savefig(output_dir / "per_node_metrics.png", dpi=180)
    plt.close(figure)

    for field, title, unit, color in METRICS:
        values = [float(record[field]) if record[field] is not None else float("nan") for record in records]
        fleet_mean = mean(values)
        figure, axis = plt.subplots(figsize=(13, 6), constrained_layout=True)
        axis.bar(range(len(nodes)), values, color=color)
        axis.set_title(f"Mixer D-Cube per-node average: {title} ({round_label})")
        axis.set_xlabel("Observer ID")
        axis.set_ylabel(unit)
        axis.set_xticks(range(len(nodes)))
        axis.set_xticklabels(nodes, rotation=90, fontsize=8)
        axis.grid(axis="y", alpha=0.25)
        if fleet_mean is not None:
            axis.axhline(fleet_mean, color="#c0392b", linestyle="--", linewidth=1.4,
                         label=f"fleet average: {fleet_mean:.3f} {unit}")
            axis.legend()
        if field == "avg_reliability_pct":
            axis.set_ylim(0, 102)
        figure.savefig(output_dir / f"per_node_{field.removeprefix('avg_')}.png", dpi=180)
        plt.close(figure)


def print_summary(records: list[dict[str, object]], skipped: list[Path],
                  excluded_rounds: int) -> None:
    print(f"Parsed {sum(int(record['rounds']) for record in records)} round results from {len(records)} node logs.")
    if excluded_rounds:
        print(f"Excluded {excluded_rounds} round=1 result(s) from all metric averages.")
    if skipped:
        print(f"Skipped {len(skipped)} .txt file(s) with no included Mixer rounds.")
    print("\nFleet average (mean of per-node round averages):")
    for field, title, unit, _ in METRICS:
        value = mean([record[field] for record in records if isinstance(record[field], float)])
        print(f"  {title:15} {value:.3f} {unit}" if value is not None else f"  {title:15} n/a")
    print("\nPer-node averages:")
    print("  node rounds latency_ms radio_on_ms goodput_kBps reliability_pct source")
    for record in records:
        def rendered(name: str) -> str:
            value = record[name]
            return f"{value:.3f}" if isinstance(value, float) else "n/a"
        print(f"  {record['node']:>4} {record['rounds']:>6} {rendered('avg_latency_ms'):>10}"
              f" {rendered('avg_radio_on_ms'):>11} {rendered('avg_goodput_kBps'):>13}"
              f" {rendered('avg_reliability_pct'):>15} {record['metric_source']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_directory", type=Path, help="Folder containing per-node .txt logs")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory (default: <log_directory>/analysis)")
    parser.add_argument("--no-plots", action="store_true", help="Only write CSV/JSON and print results")
    parser.add_argument("--include-first-round", action="store_true",
                        help="Include round 1 in every average (excluded by default)")
    args = parser.parse_args()

    log_dir = args.log_directory.expanduser().resolve()
    if not log_dir.is_dir():
        parser.error(f"not a directory: {log_dir}")
    output_dir = (args.output_dir or log_dir / "analysis").expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rounds: list[RoundMetric] = []
    skipped: list[Path] = []
    excluded_rounds = 0
    for log_file in sorted(log_dir.rglob("*.txt")):
        parsed = parse_log(log_file, log_dir)
        included = included_rounds(parsed, args.include_first_round)
        excluded_rounds += len(parsed) - len(included)
        if included:
            rounds.extend(included)
        else:
            skipped.append(log_file)
    if not rounds:
        print("No Mixer result lines remain after round filtering.", file=sys.stderr)
        return 2

    records = per_node_averages(rounds)
    write_csv(records, output_dir / "per_node_metrics.csv")
    summary = {
        "node_count": len(records),
        "round_result_count": len(rounds),
        "excluded_round_result_count": excluded_rounds,
        "first_round_excluded": not args.include_first_round,
        "skipped_file_count": len(skipped),
        "fleet_averages": {
            field: mean([record[field] for record in records if isinstance(record[field], float)])
            for field, _, _, _ in METRICS
        },
    }
    (output_dir / "fleet_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print_summary(records, skipped, excluded_rounds)
    print(f"\nPer-node CSV: {output_dir / 'per_node_metrics.csv'}")
    print(f"Summary JSON:  {output_dir / 'fleet_summary.json'}")
    if not args.no_plots:
        make_plots(records, output_dir, args.include_first_round)
        print(f"Plots:         {output_dir / 'per_node_metrics.png'} and per_node_<metric>.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
