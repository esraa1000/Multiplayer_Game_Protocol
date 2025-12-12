#!/usr/bin/env python3
"""
Generate comprehensive statistics report for all test scenarios
Reports mean, median, and 95th percentile for latency, jitter, and position error
"""

import csv
import sys
from collections import defaultdict

def percentile(data, p):
    """Calculate percentile"""
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 0:
        return 0
    k = (n - 1) * p / 100.0
    f = int(k)
    c = f + 1
    if c >= n:
        return sorted_data[-1]
    d0 = sorted_data[f] * (c - k)
    d1 = sorted_data[c] * (k - f)
    return d0 + d1

def mean(data):
    return sum(data) / len(data) if data else 0

def median(data):
    return percentile(data, 50)

def analyze_scenario(csv_file, scenario_name):

    metrics_by_client = defaultdict(list)

    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                client_id = int(row['client_id'])
                metrics_by_client[client_id].append({
                    'latency_ms': float(row['latency_ms']),
                    'jitter_ms': float(row['jitter_ms']),
                    'perceived_position_error': float(row['perceived_position_error']),
                })
    except FileNotFoundError:
        print(f"Error: File not found: {csv_file}")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

    all_latencies = []
    all_jitters = []
    all_errors = []

    for client_id, metrics in metrics_by_client.items():
        all_latencies.extend([m['latency_ms'] for m in metrics])
        all_jitters.extend([m['jitter_ms'] for m in metrics])
        all_errors.extend([m['perceived_position_error'] for m in metrics])

    if not all_latencies:
        print(f"No data found in {csv_file}")
        return None

    stats = {
        'scenario': scenario_name,
        'num_clients': len(metrics_by_client),
        'total_samples': len(all_latencies),

        'latency_mean': mean(all_latencies),
        'latency_median': median(all_latencies),
        'latency_p95': percentile(all_latencies, 95),
        'latency_max': max(all_latencies),

        'jitter_mean': mean(all_jitters),
        'jitter_median': median(all_jitters),
        'jitter_p95': percentile(all_jitters, 95),
        'jitter_max': max(all_jitters),

        'error_mean': mean(all_errors),
        'error_median': median(all_errors),
        'error_p95': percentile(all_errors, 95),
        'error_max': max(all_errors),
    }

    return stats


def print_statistics(stats):
    if not stats:
        return

    print(f"\n{'='*80}")
    print(f"SCENARIO: {stats['scenario'].upper()}")
    print(f"{'='*80}")
    print(f"Clients: {stats['num_clients']}")
    print(f"Total Samples: {stats['total_samples']}")
    print(f"\n{'-'*80}")
    print(f"{'Metric':<30} {'Mean':>10} {'Median':>10} {'95th %ile':>10} {'Max':>10}")
    print(f"{'-'*80}")

    print(f"{'Latency (ms)':<30} {stats['latency_mean']:>10.2f} {stats['latency_median']:>10.2f} "
          f"{stats['latency_p95']:>10.2f} {stats['latency_max']:>10.2f}")

    print(f"{'Jitter (ms)':<30} {stats['jitter_mean']:>10.2f} {stats['jitter_median']:>10.2f} "
          f"{stats['jitter_p95']:>10.2f} {stats['jitter_max']:>10.2f}")

    print(f"{'Position Error (units)':<30} {stats['error_mean']:>10.3f} {stats['error_median']:>10.3f} "
          f"{stats['error_p95']:>10.3f} {stats['error_max']:>10.3f}")

    print(f"{'-'*80}\n")


def generate_summary_table(all_stats):

    print(f"\n{'='*100}")
    print(f"SUMMARY TABLE - ALL SCENARIOS")
    print(f"{'='*100}")

    print(f"\nLATENCY (ms)")
    print(f"{'-'*100}")
    print(f"{'Scenario':<15} {'Mean':>12} {'Median':>12} {'95th %ile':>12} {'Max':>12}")
    print(f"{'-'*100}")
    for stats in all_stats:
        print(f"{stats['scenario']:<15} {stats['latency_mean']:>12.2f} {stats['latency_median']:>12.2f} "
              f"{stats['latency_p95']:>12.2f} {stats['latency_max']:>12.2f}")

    print(f"\nJITTER (ms)")
    print(f"{'-'*100}")
    print(f"{'Scenario':<15} {'Mean':>12} {'Median':>12} {'95th %ile':>12} {'Max':>12}")
    print(f"{'-'*100}")
    for stats in all_stats:
        print(f"{stats['scenario']:<15} {stats['jitter_mean']:>12.2f} {stats['jitter_median']:>12.2f} "
              f"{stats['jitter_p95']:>12.2f} {stats['jitter_max']:>12.2f}")

    print(f"\nPOSITION ERROR (units)")
    print(f"{'-'*100}")
    print(f"{'Scenario':<15} {'Mean':>12} {'Median':>12} {'95th %ile':>12} {'Max':>12}")
    print(f"{'-'*100}")
    for stats in all_stats:
        print(f"{stats['scenario']:<15} {stats['error_mean']:>12.3f} {stats['error_median']:>12.3f} "
              f"{stats['error_p95']:>12.3f} {stats['error_max']:>12.3f}")

    print(f"{'='*100}\n")


def save_statistics_csv(all_stats, output_file='results/statistics_summary.csv'):

    if not all_stats:
        return

    try:
        with open(output_file, 'w', newline='') as f:
            fieldnames = [
                'scenario', 'num_clients', 'total_samples',
                'latency_mean', 'latency_median', 'latency_p95', 'latency_max',
                'jitter_mean', 'jitter_median', 'jitter_p95', 'jitter_max',
                'error_mean', 'error_median', 'error_p95', 'error_max'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for stats in all_stats:
                writer.writerow(stats)

        print(f"Statistics saved to: {output_file}\n")
    except Exception as e:
        print(f"Error saving statistics CSV: {e}")


def main():

    scenarios = ['baseline', 'loss2', 'loss5', 'delay100']
    results_dir = 'results'

    all_stats = []

    for scenario in scenarios:
        csv_file = f"{results_dir}/client_metrics_{scenario}.csv"
        stats = analyze_scenario(csv_file, scenario)

        if stats:
            all_stats.append(stats)
            print_statistics(stats)

    if all_stats:

        generate_summary_table(all_stats)
        save_statistics_csv(all_stats)

        print(f"\n{'='*100}")
        print("REQUIREMENTS CHECK")
        print(f"{'='*100}")

        for stats in all_stats:
            scenario = stats['scenario']
            print(f"\n{scenario.upper()}:")

            if scenario == 'baseline':
                print(f"  Latency mean: {stats['latency_mean']:.2f}ms (need ≤50ms) - "
                      f"{'✅ PASS' if stats['latency_mean'] <= 50 else '❌ FAIL'}")

            elif scenario == 'loss2':
                print(f"  Error mean: {stats['error_mean']:.3f} units (need ≤0.5) - "
                      f"{'✅ PASS' if stats['error_mean'] <= 0.5 else '❌ FAIL'}")
                print(f"  Error 95th%: {stats['error_p95']:.3f} units (need ≤1.5) - "
                      f"{'✅ PASS' if stats['error_p95'] <= 1.5 else '❌ FAIL'}")

            elif scenario == 'loss5':
                ok = stats['latency_p95'] <= 200
                print(f"  Latency 95th%: {stats['latency_p95']:.2f}ms (need ≤200ms) - "
                      f"{'✅ PASS' if ok else '❌ FAIL'}")

            # ✅ FIXED: DELAY100 NOW PRINTS IN TERMINAL
            elif scenario == 'delay100':
                print(f"  Latency mean: {stats['latency_mean']:.2f}ms")
                print(f"  Latency 95th%: {stats['latency_p95']:.2f}ms")
                print(f"  Jitter mean: {stats['jitter_mean']:.2f}ms")
                print(f"  Error mean: {stats['error_mean']:.3f} units")

        print(f"\n{'='*100}\n")

    else:
        print("No statistics generated. Check that result files exist.")


if __name__ == "__main__":
    main()
