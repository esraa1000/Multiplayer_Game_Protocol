import socket
import struct
import time
import argparse
import csv
import threading
import psutil
import signal
import sys
import random
from protocol_constants import *
from client_utils import parse_and_validate_header, parse_snapshot_payload, current_time_ms
import server_utils

SERVER_ADDR = ("127.0.0.1", 9999)
GRID_SIZE = 5
SNAPSHOT_RATE = 20
BUFFER_SIZE = 4096

player_id = None
running = True
last_snapshot_id = -1
current_grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
metrics = []
stop_event = threading.Event()
pending_events = {}
metrics_lock = threading.Lock()
output_csv_path = None


def save_metrics():
    """Save metrics to CSV - called on exit"""
    global metrics, output_csv_path
    
    if not output_csv_path:
        return
        
    with metrics_lock:
        if metrics:
            try:
                with open(output_csv_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
                    writer.writeheader()
                    for row in metrics:
                        writer.writerow(row)
                print(f"[CLIENT] Saved {len(metrics)} metrics to {output_csv_path}")
            except Exception as e:
                print(f"[CLIENT] Error saving metrics: {e}")
        else:
            try:
                with open(output_csv_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'client_id', 'snapshot_id', 'seq_num', 'server_timestamp_ms',
                        'recv_time_ms', 'latency_ms', 'jitter_ms', 'perceived_position_error',
                        'cpu_percent', 'bandwidth_per_client_kbps'
                    ])
                    writer.writeheader()
                print(f"[CLIENT] No metrics collected, created empty file: {output_csv_path}")
            except Exception as e:
                print(f"[CLIENT] Error creating empty metrics file: {e}")


def signal_handler(sig, frame):
    """Handle termination signals gracefully"""
    global running
    print(f"[CLIENT] Received signal {sig}, shutting down...")
    running = False
    stop_event.set()
    save_metrics()
    sys.exit(0)


def connect(sock):
    """Connect to server with INIT/INIT_ACK handshake"""
    global player_id
    for attempt in range(10):
        try:
            nonce = current_time_ms()
            payload = struct.pack("!Q16s", nonce, b"HeadlessClient")
            seq = int(time.time() * 1000) & 0xffffffff
            server_utils.send_packet(sock, SERVER_ADDR, MSG_INIT, 0, payload, seq)
            sock.settimeout(0.5 + attempt * 0.2)
            data, _ = sock.recvfrom(BUFFER_SIZE)
            parsed = parse_and_validate_header(data)
            if parsed and parsed['msg_type'] == MSG_INIT_ACK:
                client_nonce, pid, _, _ = struct.unpack('!Q I I Q', parsed["payload"][:24])
                if client_nonce == nonce:
                    player_id = pid
                    print(f"[CLIENT] Connected as Player {player_id}")
                    return True
        except socket.timeout:
            print(f"[CLIENT] Timeout connecting (attempt {attempt+1}/10)")
        except Exception as e:
            print(f"[CLIENT] Connect error: {e}")
    print("[CLIENT] All connection attempts failed")
    return False


def simulate_user_clicks(sock):
    """
    Simulate a human player clicking on grid cells.
    Click on random empty cells with some delay between clicks.
    This matches the interactive GUI behavior.
    """
    print(f"[CLIENT] Player {player_id} starting to play...")
    
    while not stop_event.is_set():
        # Find empty cells that this player can claim
        empty_cells = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if current_grid[r][c] == 0:
                    empty_cells.append((r, c))
        
        if empty_cells:
            # Pick a random empty cell to "click"
            r, c = random.choice(empty_cells)
            
            # Send event for this cell
            payload = struct.pack("!Q H H", current_time_ms(), r, c)
            seq = int(time.time() * 1000) & 0xffffffff
            server_utils.send_packet(sock, SERVER_ADDR, MSG_EVENT, 0, payload, seq)
            pending_events[(r, c)] = {'sent_ts': current_time_ms(), 'retries': 0}
            
            # Human-like delay between clicks (200-500ms)
            time.sleep(random.uniform(0.2, 0.5))
        else:
            # Grid is full, wait a bit
            time.sleep(0.1)


def retransmit_loop(sock):
    """Retransmit pending events for reliability"""
    while not stop_event.is_set():
        time.sleep(0.05)
        now = current_time_ms()
        for (r, c), info in list(pending_events.items()):
            if info['retries'] >= 5:
                pending_events.pop((r, c), None)
                continue
            if now - info['sent_ts'] > 100:  # 100ms retransmit
                payload = struct.pack("!Q H H", current_time_ms(), r, c)
                seq = int(time.time() * 1000) & 0xffffffff
                server_utils.send_packet(sock, SERVER_ADDR, MSG_EVENT, 0, payload, seq)
                info['sent_ts'] = now
                info['retries'] += 1


def resolve_pending_events():
    """Remove events that are reflected in grid"""
    for key in list(pending_events.keys()):
        r, c = key
        if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE and current_grid[r][c] != 0:
            pending_events.pop(key, None)


def calculate_position_error(server_grid, client_grid):
    """
    Calculate perceived position error between server and client grids.
    This represents how many cells differ between what server says and what client has.
    """
    differences = 0
    
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if server_grid[r][c] != client_grid[r][c]:
                differences += 1
    
    # Normalize to 0-10 scale
    total_cells = GRID_SIZE * GRID_SIZE
    error = (differences / total_cells) * 10.0
    
    return error


def receive_loop(sock, duration, scenario):
    global last_snapshot_id, current_grid, running
    
    sock.settimeout(0.05)
    start_time = time.time()
    last_latency = None
    packet_count = 0
    missed_snapshots = 0

    position_log = None
    try:
        position_log = open('client_positions.csv', 'w')
        position_log.write("timestamp,snapshot_id,grid_flat\n")
    except:
        pass

    # Start simulated user interaction thread (matches GUI click behavior)
    click_thread = threading.Thread(target=simulate_user_clicks, args=(sock,), daemon=True)
    retrans_thread = threading.Thread(target=retransmit_loop, args=(sock,), daemon=True)
    click_thread.start()
    retrans_thread.start()

    while time.time() - start_time < duration and running:
        try:
            data, _ = sock.recvfrom(BUFFER_SIZE)
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[CLIENT] Receive error: {e}")
            break
            
        parsed = parse_and_validate_header(data)
        if not parsed:
            continue

        if parsed['msg_type'] == MSG_SNAPSHOT:
            snap = parse_snapshot_payload(parsed['payload'], GRID_SIZE)
            if not snap or snap["grid"] is None:
                continue
            
            sid = snap["snapshot_id"]

            # Check for missed snapshots (packet loss)
            if last_snapshot_id >= 0:
                expected_next = last_snapshot_id + 1
                if sid > expected_next:
                    missed = sid - expected_next
                    missed_snapshots += missed
            
            # Process snapshot if it's newer
            if sid > last_snapshot_id:
                snapshot_ts = snap["server_ts"]
                recv_ts = current_time_ms()
                
                # Calculate error before updating
                old_grid = [row[:] for row in current_grid]
                error = calculate_position_error(snap["grid"], old_grid)
                
                # Update grid from server
                last_snapshot_id = sid
                current_grid = [row[:] for row in snap["grid"]]
                
                resolve_pending_events()

                latency = max(0, recv_ts - snapshot_ts)
                jitter = abs(latency - last_latency) if last_latency is not None else 0
                last_latency = latency
                
                try:
                    cpu_percent = psutil.cpu_percent(interval=None)
                except:
                    cpu_percent = 0.0
                    
                bandwidth_kbps = len(data) * 8 * SNAPSHOT_RATE / 1000

                metric = {
                    'client_id': player_id,
                    'snapshot_id': sid,
                    'seq_num': parsed['seq_num'],
                    'server_timestamp_ms': snapshot_ts,
                    'recv_time_ms': recv_ts,
                    'latency_ms': latency,
                    'jitter_ms': jitter,
                    'perceived_position_error': error,
                    'cpu_percent': cpu_percent,
                    'bandwidth_per_client_kbps': bandwidth_kbps
                }
                
                with metrics_lock:
                    metrics.append(metric)

                if position_log:
                    try:
                        grid_flat = ','.join(str(cell) for row in current_grid for cell in row)
                        position_log.write(f"{recv_ts},{sid},{grid_flat}\n")
                    except:
                        pass

                packet_count += 1
                if packet_count % 20 == 0:
                    total_expected = packet_count + missed_snapshots
                    loss_rate = (missed_snapshots / total_expected) * 100 if total_expected > 0 else 0
                    cells_claimed = sum(1 for r in range(GRID_SIZE) for c in range(GRID_SIZE) 
                                       if current_grid[r][c] == player_id)
                    print(f"[CLIENT] {scenario}: {packet_count} snapshots, {missed_snapshots} missed ({loss_rate:.1f}% loss), "
                          f"claimed {cells_claimed} cells, latency={latency:.1f}ms, error={error:.3f}")

        elif parsed['msg_type'] == MSG_GAME_OVER:
            print("[CLIENT] Game over received")
            break

    print(f"[CLIENT] Receive loop ending. Collected {len(metrics)} metrics")
    print(f"[CLIENT] Total: {packet_count} received, {missed_snapshots} missed")
    
    stop_event.set()
    running = False
    
    click_thread.join(timeout=2.0)
    retrans_thread.join(timeout=2.0)
    
    if position_log:
        position_log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless client for multiplayer game testing")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--scenario", type=str, default="baseline")
    parser.add_argument("--output_csv", type=str, required=True)
    parser.add_argument("--server_pid", type=int)
    args = parser.parse_args()

    output_csv_path = args.output_csv
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))

    if not connect(sock):
        save_metrics()
        exit(1)

    try:
        receive_loop(sock, args.duration, args.scenario)
    except Exception as e:
        print(f"[CLIENT] Error in receive loop: {e}")
    finally:
        sock.close()
        save_metrics()
        print("[CLIENT] Test completed")