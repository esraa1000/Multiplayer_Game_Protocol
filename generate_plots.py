#!/usr/bin/env python3
import os
import csv
import glob
import matplotlib.pyplot as plt
from collections import defaultdict

PLOT_DIR = "results/plots"
os.makedirs(PLOT_DIR, exist_ok=True)

SCENARIOS = ["baseline", "loss2", "loss5", "delay100"]

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def load_metrics(path):
    """Load CSV file into a list of dictionaries."""
    rows = []
    try:
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({
                    "client_id": int(row["client_id"]),
                    "snapshot_id": int(row["snapshot_id"]),
                    "seq_num": int(row["seq_num"]),
                    "server_timestamp_ms": int(row["server_timestamp_ms"]),
                    "recv_time_ms": int(row["recv_time_ms"]),
                    "latency_ms": float(row["latency_ms"]),
                    "jitter_ms": float(row["jitter_ms"]),
                    "perceived_position_error": float(row["perceived_position_error"]),
                    "cpu_percent": float(row["cpu_percent"]),
                    "bandwidth_per_client_kbps": float(row["bandwidth_per_client_kbps"]),
                })
    except Exception as e:
        print(f"[ERROR] Failed to load CSV {path}: {e}")
    return rows


def compute_update_rate(metrics):
    """Compute update rate in Hz."""
    if not metrics:
        return 0
    start = metrics[0]["recv_time_ms"]
    end = metrics[-1]["recv_time_ms"]
    duration = max(0.001, (end - start) / 1000.0)
    return len(metrics) / duration


def group_metrics_by_scenario(results_dir):
    """Load all scenario CSVs into a dict."""
    scenario_data = {}
    for s in SCENARIOS:
        path = f"{results_dir}/client_metrics_{s}.csv"
        if os.path.exists(path):
            scenario_data[s] = load_metrics(path)
        else:
            scenario_data[s] = []
    return scenario_data


# -------------------------------------------------------------------
# Plotting functions
# -------------------------------------------------------------------

def plot_metric_vs_update_rate(scenario_metrics):
    """Plots latency and jitter vs update rate for each scenario."""
    
    plt.figure(figsize=(10,6))

    for scenario, metrics in scenario_metrics.items():
        if not metrics:
            continue

        update_rate = compute_update_rate(metrics)
        avg_latency = sum(m["latency_ms"] for m in metrics) / len(metrics)
        avg_jitter = sum(m["jitter_ms"] for m in metrics) / len(metrics)

        plt.scatter(update_rate, avg_latency, label=f"{scenario} (latency)", s=80)
        plt.scatter(update_rate, avg_jitter, label=f"{scenario} (jitter)", marker="x", s=80)

    plt.title("Latency & Jitter vs Update Rate")
    plt.xlabel("Update Rate (Hz)")
    plt.ylabel("Latency / Jitter (ms)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/latency_jitter_vs_update_rate.png")
    print("Saved: latency_jitter_vs_update_rate.png")


def plot_error_vs_loss_rate(scenario_metrics):
    """Plots perceived position error vs loss rate."""
    scenarios = []
    avg_errors = []

    for scenario, metrics in scenario_metrics.items():
        if not metrics:
            continue
        err = sum(m["perceived_position_error"] for m in metrics) / len(metrics)
        scenarios.append(scenario)
        avg_errors.append(err)

    plt.figure(figsize=(8,5))
    plt.bar(scenarios, avg_errors, color=["green","orange","red","blue"])
    plt.title("Perceived Position Error vs Network Condition")
    plt.xlabel("Scenario")
    plt.ylabel("Mean Position Error")
    plt.grid(axis="y")

    plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/position_error_vs_scenario.png")
    print("Saved: position_error_vs_scenario.png")


def plot_bandwidth_comparison(scenario_metrics):
    """Plot average bandwidth per scenario."""
    scenarios = []
    bw_values = []

    for scenario, metrics in scenario_metrics.items():
        if not metrics:
            continue
        bw = sum(m["bandwidth_per_client_kbps"] for m in metrics) / len(metrics)
        scenarios.append(scenario)
        bw_values.append(bw)

    plt.figure(figsize=(8,5))
    plt.bar(scenarios, bw_values, color="purple")
    plt.title("Bandwidth Usage per Scenario")
    plt.xlabel("Scenario")
    plt.ylabel("Bandwidth (kbps)")
    plt.grid(axis="y")

    plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/bandwidth_per_scenario.png")
    print("Saved: bandwidth_per_scenario.png")


# -------------------------------------------------------------------
# Main entry point
# -------------------------------------------------------------------

def generate_all_plots(results_dir="results"):
    print("\n=== ChronoClash Plot Generation ===")

    scenario_metrics = group_metrics_by_scenario(results_dir)

    print("Loaded metrics for scenarios:")
    for s, m in scenario_metrics.items():
        print(f" - {s}: {len(m)} rows")

    print("\nGenerating plots...")
    plot_metric_vs_update_rate(scenario_metrics)
    plot_error_vs_loss_rate(scenario_metrics)
    plot_bandwidth_comparison(scenario_metrics)

    print(f"\nAll plots saved to: {PLOT_DIR}/\n")


if __name__ == "__main__":
    generate_all_plots()
