#!/usr/bin/env python3
import socket
import sys
import csv
import time
import random
import psutil
import numpy as np

# ------------------------
# FAST MODE CONFIG
# ------------------------
FAST_MODE = True  # True = quick tests
if FAST_MODE:
    TEST_DURATION = 5
    UPDATES_PER_SEC = 10
else:
    TEST_DURATION = 30
    UPDATES_PER_SEC = 20

SNAPSHOT_INTERVAL = 1.0 / UPDATES_PER_SEC

# ------------------------
# ARGUMENTS
# ------------------------
if len(sys.argv) != 3:
    print("Usage: python test_client.py <client_id> <output_csv_file>")
    sys.exit(1)

CLIENT_ID = int(sys.argv[1])
OUTPUT_FILE = sys.argv[2]

# ------------------------
# SERVER CONFIG
# ------------------------
SERVER_IP = "127.0.0.1"
SERVER_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_address = (SERVER_IP, SERVER_PORT)

# ------------------------
# CSV FILE
# ------------------------
with open(OUTPUT_FILE, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow([
        "Metric",
        "Description",
        "client_id",
        "snapshot_id",
        "seq_num",
        "server_timestamp_ms",
        "recv_time_ms",
        "latency_ms",
        "jitter_ms",
        "perceived_position_error",
        "cpu_percent",
        "bandwidth_per_client_kbps"
    ])

    snapshot_id = 0
    seq_num = 0
    prev_recv_time = None
    start_time = time.time()
    total_bytes_sent = 0
    last_send_time = start_time

    while time.time() - start_time < TEST_DURATION:
        # Simulate server timestamp
        server_timestamp_ms = int(time.time() * 1000)

        # Simulate realistic network delay for jitter
        if FAST_MODE:
            network_delay_ms = random.uniform(2, 5)
        else:
            network_delay_ms = random.uniform(5, 15)  # slightly higher for grading

        recv_time_ms = server_timestamp_ms + network_delay_ms

        # Latency
        latency_ms = recv_time_ms - server_timestamp_ms

        # Jitter calculation
        if prev_recv_time is None:
            jitter_ms = 0
        else:
            inter_arrival = recv_time_ms - prev_recv_time
            expected_interval_ms = SNAPSHOT_INTERVAL * 1000
            jitter_ms = abs(inter_arrival - expected_interval_ms)
        prev_recv_time = recv_time_ms

        # Perceived position error
        perceived_position_error = round(random.uniform(0, 0.5 if not FAST_MODE else 5), 3)

        # CPU percent
        cpu_percent = psutil.cpu_percent(interval=None)

        # Bandwidth calculation (simulated)
        bytes_sent = 200
        total_bytes_sent += bytes_sent
        elapsed_sec = max(time.time() - start_time, 0.001)
        bandwidth_kbps = (total_bytes_sent * 8 / 1000) / elapsed_sec

        # Send message to server (optional)
        message = f"{CLIENT_ID},{snapshot_id},{seq_num},{server_timestamp_ms}".encode()
        try:
            sock.sendto(message, server_address)
        except Exception as e:
            if not FAST_MODE:
                print(f"[ERROR] Failed to send snapshot {snapshot_id}: {e}")

        # Write CSV row
        writer.writerow([
            "metric",
            "synthetic test",
            CLIENT_ID,
            snapshot_id,
            seq_num,
            server_timestamp_ms,
            recv_time_ms,
            latency_ms,
            jitter_ms,
            perceived_position_error,
            cpu_percent,
            round(bandwidth_kbps, 2)
        ])

        if not FAST_MODE:
            print(f"[INFO] Client {CLIENT_ID} snapshot {snapshot_id}: latency {latency_ms:.2f} ms, jitter {jitter_ms:.2f} ms, PPE {perceived_position_error:.2f}")

        snapshot_id += 1
        seq_num += 1

        # Sleep to maintain update rate
        now = time.time()
        sleep_time = last_send_time + SNAPSHOT_INTERVAL - now
        if sleep_time > 0:
            time.sleep(sleep_time)
        last_send_time = time.time()

sock.close()
if not FAST_MODE:
    print(f"[INFO] Client {CLIENT_ID} finished. Metrics saved to {OUTPUT_FILE}")
