#!/usr/bin/env python3
import subprocess
import time
import os
import signal
import csv
import psutil
import sys
import platform
import numpy as np

# ------------------------
# CONFIG
# ------------------------
FAST_MODE = True  
PYTHON_CMD = sys.executable
SERVER_CMD = [PYTHON_CMD, "server.py"]
RESULTS_DIR = "results"

if FAST_MODE:
    NUM_CLIENTS = 2
    TEST_DURATION = 5
    UPDATES_PER_SEC = 10
else:
    NUM_CLIENTS = 4
    TEST_DURATION = 30
    UPDATES_PER_SEC = 20

# ------------------------
# NETWORK INTERFACE FOR NETEM
# ------------------------
IFACE = "eth0"  # Change to your interface

# ------------------------
# NETWORK IMPAIRMENT FUNCTIONS
# ------------------------
def apply_netem_loss(iface, loss_percent):
    cmd = f"sudo tc qdisc add dev {iface} root netem loss {loss_percent}%"
    subprocess.run(cmd, shell=True, check=True)
    print(f"[INFO] Applied {loss_percent}% packet loss on {iface}")

def apply_netem_delay(iface, delay_ms):
    cmd = f"sudo tc qdisc add dev {iface} root netem delay {delay_ms}ms"
    subprocess.run(cmd, shell=True, check=True)
    print(f"[INFO] Applied {delay_ms}ms delay on {iface}")

def clear_netem(iface):
    cmd = f"sudo tc qdisc del dev {iface} root"
    subprocess.run(cmd, shell=True, check=True)
    print(f"[INFO] Cleared netem on {iface}")

# ------------------------
# SERVER FUNCTIONS
# ------------------------
def start_server():
    print("[INFO] Starting server...")
    system_platform = platform.system()
    if system_platform == "Windows":
        server = subprocess.Popen(
            SERVER_CMD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        server = subprocess.Popen(
            SERVER_CMD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
    time.sleep(1.0 if FAST_MODE else 1.5)
    print("[INFO] Server PID:", server.pid)
    return server

def stop_server(server_proc):
    system_platform = platform.system()
    if system_platform == "Windows":
        server_proc.send_signal(signal.CTRL_BREAK_EVENT)
        server_proc.terminate()
    else:
        os.killpg(os.getpgid(server_proc.pid), signal.SIGTERM)

# ------------------------
# CLIENT FUNCTIONS
# ------------------------
def start_client(client_id):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_file = f"{RESULTS_DIR}/client_{client_id}.csv"
    cmd = [PYTHON_CMD, "test_client.py", str(client_id), output_file]
    print(f"[INFO] Starting client {client_id}...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc

# ------------------------
# CPU MONITORING
# ------------------------
def collect_cpu_usage(server_pid, duration):
    process = psutil.Process(server_pid)
    cpu_samples = []
    start = time.time()
    print("[INFO] Tracking CPU usage...")
    while time.time() - start < duration:
        time.sleep(1)
        try:
            cpu_samples.append(process.cpu_percent(interval=None))
        except psutil.NoSuchProcess:
            break
    return sum(cpu_samples)/len(cpu_samples) if cpu_samples else 0.0

# ------------------------
# CSV MERGE
# ------------------------
def merge_client_metrics():
    merged_file = f"{RESULTS_DIR}/merged_metrics.csv"
    print("[INFO] Merging client CSVs ->", merged_file)
    rows = []
    header_written = False
    for cid in range(NUM_CLIENTS):
        filename = f"{RESULTS_DIR}/client_{cid}.csv"
        if not os.path.exists(filename):
            continue
        with open(filename, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            if not header_written:
                with open(merged_file, "w", newline="") as out:
                    csv.writer(out).writerow(header)
                header_written = True
            for row in reader:
                rows.append(row)
    with open(merged_file, "a", newline="") as out:
        writer = csv.writer(out)
        for row in rows:
            writer.writerow(row)
    print("[INFO] Merged CSV saved!")
    return merged_file

# ------------------------
# SUMMARY
# ------------------------
def compute_summary(merged_file):
    print("[INFO] Computing summary metrics...")
    latencies, jitters, cpu_list, bw_list, ppe_list = [], [], [], [], []

    with open(merged_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            latencies.append(float(row["latency_ms"]))
            jitters.append(float(row["jitter_ms"]))
            cpu_list.append(float(row["cpu_percent"]))
            bw_list.append(float(row["bandwidth_per_client_kbps"]))
            ppe_list.append(float(row["perceived_position_error"]))

    latencies = np.array(latencies)
    jitters = np.array(jitters)
    cpu_list = np.array(cpu_list)
    bw_list = np.array(bw_list)
    ppe_list = np.array(ppe_list)

    avg_latency = np.mean(latencies) if len(latencies) else 0
    avg_jitter = np.mean(jitters) if len(jitters) else 0
    avg_cpu = np.mean(cpu_list) if len(cpu_list) else 0
    avg_bw = np.mean(bw_list) if len(bw_list) else 0
    mean_ppe = np.mean(ppe_list) if len(ppe_list) else 0
    p95_ppe = np.percentile(ppe_list, 95) if len(ppe_list) else 0

    critical_events = np.sum(latencies <= 200)
    total_events = len(latencies)
    critical_success_rate = (critical_events / total_events * 100) if total_events else 0

    summary_file = f"{RESULTS_DIR}/summary.txt"
    with open(summary_file, "w") as f:
        f.write("=== BASELINE TEST SUMMARY ===\n")
        f.write(f"Average Latency: {avg_latency:.2f} ms\n")
        f.write(f"Average Jitter: {avg_jitter:.2f} ms\n")
        f.write(f"Average CPU: {avg_cpu:.2f}%\n")
        f.write(f"Average Bandwidth per Client: {avg_bw:.2f} kbps\n")
        f.write(f"Mean Perceived Position Error: {mean_ppe:.2f} units\n")
        f.write(f"95th Percentile PPE: {p95_ppe:.2f} units\n")
        f.write(f"Critical Event Delivery <=200ms: {critical_success_rate:.2f}%\n")
        f.write(f"Total Snapshots: {total_events}\n")
        f.write(f"Test Duration: {TEST_DURATION} sec\n")

    print("[INFO] Summary saved to", summary_file)

# ------------------------
# RUN TEST
# ------------------------
def run_test(test_name):
    print(f"\n\n=== RUNNING TEST: {test_name} ===")
    server_proc = start_server()
    client_procs = [start_client(cid) for cid in range(NUM_CLIENTS)]

    cpu_avg = collect_cpu_usage(server_proc.pid, TEST_DURATION)

    for p in client_procs:
        p.wait()

    print("[INFO] Stopping server...")
    stop_server(server_proc)

    merged = merge_client_metrics()
    compute_summary(merged)

    with open(f"{RESULTS_DIR}/cpu_usage.txt", "w") as f:
        f.write(f"Average CPU Usage: {cpu_avg:.2f}%\n")

    print(f"=== TEST {test_name} COMPLETE ===")

# ------------------------
# MAIN
# ------------------------
if __name__ == "__main__":
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # 1. Baseline test
    run_test("BASELINE (NO IMPAIRMENT)")

    # 2. LAN-like 2% loss
    try:
        apply_netem_loss(IFACE, 2)
        run_test("LAN LOSS 2%")
    finally:
        clear_netem(IFACE)

    # 3. WAN-like 5% loss
    try:
        apply_netem_loss(IFACE, 5)
        run_test("WAN LOSS 5%")
    finally:
        clear_netem(IFACE)

    # 4. WAN delay 100ms
    try:
        apply_netem_delay(IFACE, 100)
        run_test("WAN DELAY 100ms")
    finally:
        clear_netem(IFACE)
