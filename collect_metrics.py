import sys
import csv
import re

if len(sys.argv) != 3:
    print("Usage: python3 collect_metrics.py <log_file> <output_csv>")
    sys.exit(1)

log_file = sys.argv[1]
output_csv = sys.argv[2]

latencies = []
errors = []
timestamps = []

with open(log_file, "r") as f:
    for line in f:
        match = re.search(r"Latency:\s*(\d+\.?\d*)\s*ms.*Error:\s*(\d+\.?\d*)", line)
        if match:
            latencies.append(float(match.group(1)))
            errors.append(float(match.group(2)))
            timestamps.append(len(timestamps))

# Save to CSV
with open(output_csv, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["timestamp", "latency_ms", "error_units"])
    for i in range(len(latencies)):
        writer.writerow([timestamps[i], latencies[i], errors[i]])

print(f"Metrics collected and saved to {output_csv}")
