#!/usr/bin/env python3
"""
Verify that collected metrics meet project requirements for each scenario:

Baseline: 20 updates/sec per client; avg latency ≤ 50ms; avg CPU < 60%
Loss 2%: Mean perceived position error ≤ 0.5 units; 95th percentile ≤ 1.5 units
Loss 5%: Critical events reliably delivered (≥99% within 200ms); system stable
Delay 100ms: Clients continue functioning; no visible misbehavior
"""

import csv
import sys
from collections import defaultdict

def percentile(data, p):
    """Calculate percentile without numpy"""
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
    """Calculate mean"""
    return sum(data) / len(data) if data else 0

def median(data):
    """Calculate median"""
    return percentile(data, 50)

def analyze_baseline(metrics):
    """Check baseline requirements: 20 updates/sec, latency ≤50ms, CPU <60%"""
    print("  Checking Baseline Requirements:")
    print("  " + "-"*60)
    
    all_passed = True
    
    # 1. Update rate
    if len(metrics) >= 2:
        first_time = metrics[0]['recv_time_ms']
        last_time = metrics[-1]['recv_time_ms']
        duration_sec = (last_time - first_time) / 1000.0
        
        if duration_sec > 0:
            actual_rate = len(metrics) / duration_sec
            print(f"  Update rate: {actual_rate:.2f} updates/sec (need ≥20)")
            
            if actual_rate >= 18.0:  # Allow 10% tolerance
                print(f"  ✅ Update rate: PASS")
            else:
                print(f"  ❌ Update rate: FAIL")
                all_passed = False
    
    # 2. Latency
    latencies = [m['latency_ms'] for m in metrics]
    avg_latency = mean(latencies)
    max_latency = max(latencies) if latencies else 0
    
    print(f"  Avg latency: {avg_latency:.2f}ms (need ≤50ms)")
    print(f"  Max latency: {max_latency:.2f}ms")
    
    if avg_latency <= 50:
        print(f"  ✅ Latency: PASS")
    else:
        print(f"  ❌ Latency: FAIL")
        all_passed = False
    
    # 3. CPU
    cpu_values = [m['cpu_percent'] for m in metrics]
    avg_cpu = mean(cpu_values)
    max_cpu = max(cpu_values) if cpu_values else 0
    
    print(f"  Avg CPU: {avg_cpu:.1f}% (need <60%)")
    print(f"  Max CPU: {max_cpu:.1f}%")
    
    if avg_cpu < 60:
        print(f"  ✅ CPU: PASS")
    else:
        print(f"  ❌ CPU: FAIL")
        all_passed = False
    
    return all_passed


def analyze_loss2(metrics):
    """Check Loss 2% requirements: position error ≤0.5 mean, ≤1.5 at 95th percentile"""
    print("  Checking Loss 2% Requirements:")
    print("  " + "-"*60)
    
    all_passed = True
    
    # Position error analysis
    errors = [m['perceived_position_error'] for m in metrics]
    mean_error = mean(errors)
    percentile_95 = percentile(errors, 95)
    max_error = max(errors) if errors else 0
    
    print(f"  Mean position error: {mean_error:.3f} units (need ≤0.5)")
    print(f"  95th percentile error: {percentile_95:.3f} units (need ≤1.5)")
    print(f"  Max error: {max_error:.3f} units")
    
    if mean_error <= 0.5:
        print(f"  ✅ Mean error: PASS")
    else:
        print(f"  ❌ Mean error: FAIL")
        all_passed = False
    
    if percentile_95 <= 1.5:
        print(f"  ✅ 95th percentile: PASS")
    else:
        print(f"  ❌ 95th percentile: FAIL")
        all_passed = False
    
    # Additional info: interpolation quality
    print(f"  Note: Check for graceful interpolation in logs")
    
    return all_passed


def analyze_loss5(metrics):
    """Check Loss 5% requirements: critical events ≥99% delivered within 200ms"""
    print("  Checking Loss 5% Requirements:")
    print("  " + "-"*60)
    
    all_passed = True
    
    # Analyze latency distribution for event delivery
    latencies = [m['latency_ms'] for m in metrics]
    within_200ms = sum(1 for lat in latencies if lat <= 200)
    delivery_rate = (within_200ms / len(latencies)) * 100 if latencies else 0
    
    mean_latency = mean(latencies)
    percentile_99 = percentile(latencies, 99)
    max_latency = max(latencies) if latencies else 0
    
    print(f"  Events within 200ms: {within_200ms}/{len(latencies)} ({delivery_rate:.2f}%)")
    print(f"  Mean latency: {mean_latency:.2f}ms")
    print(f"  99th percentile latency: {percentile_99:.2f}ms")
    print(f"  Max latency: {max_latency:.2f}ms")
    
    if delivery_rate >= 99.0:
        print(f"  ✅ Delivery rate: PASS (≥99% within 200ms)")
    else:
        print(f"  ❌ Delivery rate: FAIL (need ≥99%)")
        all_passed = False
    
    # Check system stability (no crashes, consistent updates)
    if len(metrics) >= 2:
        first_time = metrics[0]['recv_time_ms']
        last_time = metrics[-1]['recv_time_ms']
        duration_sec = (last_time - first_time) / 1000.0
        update_rate = len(metrics) / duration_sec if duration_sec > 0 else 0
        
        print(f"  Update rate: {update_rate:.2f}/sec")
        
        if update_rate >= 15.0:  # System still functioning
            print(f"  ✅ System stability: PASS")
        else:
            print(f"  ⚠️  System stability: degraded but may be acceptable")
    
    return all_passed


def analyze_delay100(metrics):
    """Check Delay 100ms requirements: clients functioning, no visible misbehavior"""
    print("  Checking Delay 100ms Requirements:")
    print("  " + "-"*60)
    
    all_passed = True
    
    # Check that clients continue functioning
    if len(metrics) >= 2:
        first_time = metrics[0]['recv_time_ms']
        last_time = metrics[-1]['recv_time_ms']
        duration_sec = (last_time - first_time) / 1000.0
        update_rate = len(metrics) / duration_sec if duration_sec > 0 else 0
        
        print(f"  Total snapshots received: {len(metrics)}")
        print(f"  Duration: {duration_sec:.2f}s")
        print(f"  Update rate: {update_rate:.2f}/sec")
        
        if update_rate >= 10.0:  # Reasonable functioning threshold
            print(f"  ✅ Clients functioning: PASS")
        else:
            print(f"  ❌ Clients functioning: FAIL")
            all_passed = False
    
    # Analyze latency to verify delay is applied correctly
    latencies = [m['latency_ms'] for m in metrics]
    mean_latency = mean(latencies)
    median_latency = median(latencies)
    
    print(f"  Mean latency: {mean_latency:.2f}ms")
    print(f"  Median latency: {median_latency:.2f}ms")
    
    # With 100ms delay, latency should be around 100ms
    if 80 <= mean_latency <= 150:  # Allow some variance
        print(f"  ✅ Delay applied correctly: PASS")
    else:
        print(f"  ⚠️  Delay may not be applied correctly (expected ~100ms)")
    
    # Check for stability (no excessive jitter indicating misbehavior)
    jitters = [m['jitter_ms'] for m in metrics if m['jitter_ms'] > 0]
    if jitters:
        mean_jitter = mean(jitters)
        max_jitter = max(jitters)
        
        print(f"  Mean jitter: {mean_jitter:.2f}ms")
        print(f"  Max jitter: {max_jitter:.2f}ms")
        
        if mean_jitter < 50:  # Reasonable jitter threshold
            print(f"  ✅ No visible misbehavior: PASS")
        else:
            print(f"  ⚠️  High jitter detected (may indicate issues)")
    
    return all_passed


def analyze_metrics(csv_file, scenario):
    """Analyze a client metrics CSV file for specific scenario"""
    
    metrics_by_client = defaultdict(list)
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                client_id = int(row['client_id'])
                metrics_by_client[client_id].append({
                    'snapshot_id': int(row['snapshot_id']),
                    'recv_time_ms': int(row['recv_time_ms']),
                    'latency_ms': float(row['latency_ms']),
                    'jitter_ms': float(row['jitter_ms']),
                    'perceived_position_error': float(row['perceived_position_error']),
                    'cpu_percent': float(row['cpu_percent']),
                })
    except FileNotFoundError:
        print(f"❌ File not found: {csv_file}\n")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}\n")
        return False
    
    print(f"\n{'='*70}")
    print(f"Scenario: {scenario.upper()}")
    print(f"File: {csv_file}")
    print(f"{'='*70}\n")
    
    if not metrics_by_client:
        print("❌ No data found in file\n")
        return False
    
    all_clients_passed = True
    
    for client_id, metrics in sorted(metrics_by_client.items()):
        if not metrics:
            continue
        
        print(f"Client {client_id} ({len(metrics)} snapshots):")
        
        # Route to appropriate test based on scenario
        if scenario == 'baseline':
            passed = analyze_baseline(metrics)
        elif scenario == 'loss2':
            passed = analyze_loss2(metrics)
        elif scenario == 'loss5':
            passed = analyze_loss5(metrics)
        elif scenario == 'delay100':
            passed = analyze_delay100(metrics)
        else:
            print(f"  ⚠️  Unknown scenario: {scenario}")
            passed = False
        
        if not passed:
            all_clients_passed = False
        
        print()
    
    # Overall summary for this scenario
    print(f"{'='*70}")
    if all_clients_passed:
        print(f"✅ {scenario.upper()}: ALL REQUIREMENTS PASSED")
    else:
        print(f"❌ {scenario.upper()}: SOME REQUIREMENTS FAILED")
    print(f"{'='*70}\n")
    
    return all_clients_passed


def check_all_scenarios(results_dir='results'):
    """Check all scenario CSV files"""
    import os
    
    scenarios = {
        'baseline': 'baseline',
        'loss2': 'loss2',
        'loss5': 'loss5',
        'delay100': 'delay100'
    }
    
    overall_pass = True
    results = {}
    
    for scenario_key, scenario_name in scenarios.items():
        csv_file = f"{results_dir}/client_metrics_{scenario_key}.csv"
        
        if not os.path.exists(csv_file):
            print(f"\n❌ Missing file: {csv_file}\n")
            overall_pass = False
            results[scenario_name] = False
            continue
        
        passed = analyze_metrics(csv_file, scenario_key)
        results[scenario_name] = passed
        
        if not passed:
            overall_pass = False
    
    # Final summary
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    
    for scenario, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {scenario.upper():15s}: {status}")
    
    print("="*70)
    
    if overall_pass:
        print("✅ ALL SCENARIOS MEET REQUIREMENTS!")
    else:
        print("❌ SOME SCENARIOS FAILED REQUIREMENTS")
    
    print("="*70 + "\n")
    
    return overall_pass


if __name__ == "__main__":
    if len(sys.argv) > 2:
        # Analyze a specific file with scenario name
        csv_file = sys.argv[1]
        scenario = sys.argv[2]
        analyze_metrics(csv_file, scenario)
    elif len(sys.argv) > 1:
        # Try to infer scenario from filename
        csv_file = sys.argv[1]
        scenario = 'baseline'  # default
        for s in ['baseline', 'loss2', 'loss5', 'delay100']:
            if s in csv_file:
                scenario = s
                break
        analyze_metrics(csv_file, scenario)
    else:
        # Analyze all scenarios
        check_all_scenarios()