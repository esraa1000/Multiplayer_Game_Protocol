# analyze_baseline_csv.py
import csv
import glob
import psutil
import time
import argparse

MAX_PLAYERS = 4

def analyze_clients(csv_pattern):
    all_metrics = []
    client_files = sorted(glob.glob(csv_pattern))[:MAX_PLAYERS]  # support up to 4 players

    for file in client_files:
        with open(file, newline='') as f:
            reader = csv.DictReader(f)
            snapshots = list(reader)
            if not snapshots:
                continue

            first_time = int(snapshots[0]['recv_time_ms'])
            last_time = int(snapshots[-1]['recv_time_ms'])
            duration_s = (last_time - first_time) / 1000.0

            snapshot_ids = [int(row['snapshot_id']) for row in snapshots]
            updates = snapshot_ids[-1] - snapshot_ids[0] + 1
            updates_per_sec = updates / duration_s if duration_s > 0 else 0

            latencies = [float(row['latency_ms']) for row in snapshots]
            avg_latency = sum(latencies) / len(latencies)
            latencies_sorted = sorted(latencies)
            latency_95 = latencies_sorted[int(0.95 * len(latencies_sorted)) - 1]

            perceived_errors = [float(row['perceived_position_error']) for row in snapshots]
            avg_error = sum(perceived_errors)/len(perceived_errors)

            all_metrics.append({
                'client_file': file,
                'updates_per_sec': updates_per_sec,
                'avg_latency': avg_latency,
                'latency_95': latency_95,
                'avg_perceived_error': avg_error
            })
    return all_metrics

def monitor_cpu(server_pid, duration=10):
    """Monitor CPU usage of the server process for the given duration in seconds."""
    p = psutil.Process(server_pid)
    cpu_samples = []
    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            cpu = p.cpu_percent(interval=0.5)
            cpu_samples.append(cpu)
        except psutil.NoSuchProcess:
            break
    avg_cpu = sum(cpu_samples)/len(cpu_samples) if cpu_samples else 0
    return avg_cpu

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv_pattern', default='headless_client_*.csv', help='Glob pattern for client CSVs')
    parser.add_argument('--server_pid', type=int, help='PID of the server process to monitor CPU')
    parser.add_argument('--cpu_duration', type=int, default=10, help='Duration to monitor server CPU in seconds')
    parser.add_argument('--output_csv', default='baseline_summary.csv', help='CSV file to store results')
    args = parser.parse_args()

    metrics = analyze_clients(args.csv_pattern)
    if not metrics:
        print("No client CSV files found.")
        return

    # Compute overall averages
    avg_updates = sum(m['updates_per_sec'] for m in metrics)/len(metrics)
    avg_latency = sum(m['avg_latency'] for m in metrics)/len(metrics)
    avg_error = sum(m['avg_perceived_error'] for m in metrics)/len(metrics)
    avg_cpu = monitor_cpu(args.server_pid, duration=args.cpu_duration) if args.server_pid else None

    # Write CSV
    with open(args.output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        # Header
        header = ['client_file','updates_per_sec','avg_latency','latency_95','avg_perceived_error']
        if avg_cpu is not None:
            header.append('server_cpu_percent')
        writer.writerow(header)

        # Per-client
        for m in metrics:
            row = [m['client_file'], f"{m['updates_per_sec']:.2f}", f"{m['avg_latency']:.2f}",
                   f"{m['latency_95']:.2f}", f"{m['avg_perceived_error']:.2f}"]
            if avg_cpu is not None:
                row.append(f"{avg_cpu:.2f}")
            writer.writerow(row)

        # Overall summary
        row = ['Overall', f"{avg_updates:.2f}", f"{avg_latency:.2f}", '', f"{avg_error:.2f}"]
        if avg_cpu is not None:
            row.append(f"{avg_cpu:.2f}")
        writer.writerow(row)

    print(f"Summary CSV saved to {args.output_csv}")
    print("Per-client metrics and overall averages included.")

if __name__ == "__main__":
    main()
