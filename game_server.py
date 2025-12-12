# game_server.py (Full implementation with all requirements)
import socket
import struct
import threading
import time
import csv
import psutil
from collections import deque, Counter
from protocol_constants import *
import server_utils

GRID_SIZE = 5
SNAPSHOT_RATE_HZ = DEFAULT_SNAPSHOT_RATE_HZ
RETRANSMIT_K = DEFAULT_REdundancy_K  # How many times to send redundant snapshots
BUFFER_SIZE = 4096
MAX_CLIENTS = 4

# Client state tracking
class ClientState:
    def __init__(self, player_id, addr, name):
        self.player_id = player_id
        self.addr = addr
        self.name = name
        self.last_ack_snapshot = -1  # Last snapshot client acknowledged
        self.last_sent_snapshot = -1  # Last snapshot sent to this client
        self.pending_snapshots = deque(maxlen=10)  # Recent snapshots not yet ACKed
        self.packet_count_sent = 0
        self.packet_count_received = 0
        self.last_seen = time.time()

clients = {}        # addr -> ClientState
player_counter = 1
grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
event_queue = deque()
lock = threading.Lock()
snapshot_id = 0
running = True
game_over = False

# Performance metrics
class PerformanceMetrics:
    def __init__(self):
        self.snapshot_count = 0
        self.event_count = 0
        self.start_time = time.time()
        self.cpu_samples = []
        self.packet_sent_count = 0
        self.packet_recv_count = 0
        
    def log_snapshot(self):
        self.snapshot_count += 1
        
    def log_event(self):
        self.event_count += 1
        
    def log_packet_sent(self):
        self.packet_sent_count += 1
        
    def log_packet_recv(self):
        self.packet_recv_count += 1
        
    def sample_cpu(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            self.cpu_samples.append(cpu)
        except:
            pass
    
    def get_stats(self):
        elapsed = time.time() - self.start_time
        return {
            'uptime_seconds': elapsed,
            'total_snapshots': self.snapshot_count,
            'total_events': self.event_count,
            'packets_sent': self.packet_sent_count,
            'packets_received': self.packet_recv_count,
            'snapshot_rate': self.snapshot_count / elapsed if elapsed > 0 else 0,
            'avg_cpu': sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0,
            'max_cpu': max(self.cpu_samples) if self.cpu_samples else 0,
        }

metrics = PerformanceMetrics()

# Logging
send_log = []  # For server_send_log.csv
recv_log = []  # For server_recv_log.csv
event_log = []  # For server_event_log.csv

def log_message(msg):
    print(msg)

def save_logs():
    """Save performance logs to CSV files"""
    try:
        # Save send log
        if send_log:
            with open('server_send_log.csv', 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['timestamp', 'msg_type', 'dest_addr', 
                                                       'snapshot_id', 'payload_size'])
                writer.writeheader()
                writer.writerows(send_log)
        
        # Save receive log
        if recv_log:
            with open('server_recv_log.csv', 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['timestamp', 'msg_type', 'src_addr', 
                                                       'payload_size'])
                writer.writeheader()
                writer.writerows(recv_log)
        
        # Save event log
        if event_log:
            with open('server_event_log.csv', 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['timestamp', 'player_id', 'row', 'col'])
                writer.writeheader()
                writer.writerows(event_log)
        
        # Save performance summary
        stats = metrics.get_stats()
        with open('server_performance.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=stats.keys())
            writer.writeheader()
            writer.writerow(stats)
        
        log_message("[SERVER] Logs saved successfully")
    except Exception as e:
        log_message(f"[SERVER] Error saving logs: {e}")

# --- Connection / INIT handling ---
def handle_init(sock, data, addr):
    global player_counter
    try:
        nonce, name_bytes = struct.unpack("!Q16s", data[:24])
        name = name_bytes.rstrip(b"\x00").decode()
    except:
        return

    with lock:
        if addr not in clients:
            if len(clients) >= MAX_CLIENTS:
                log_message(f"[SERVER] Rejected connection from {addr} (max clients reached)")
                return
            
            pid = player_counter
            clients[addr] = ClientState(pid, addr, name)
            player_counter += 1
            log_message(f"[SERVER] New player {pid} from {addr} name={name}")

    # Send INIT_ACK
    payload = struct.pack("!Q I I Q", nonce, clients[addr].player_id, 0, 0)
    seq = int(time.time() * 1000) & 0xffffffff
    server_utils.send_packet(sock, addr, MSG_INIT_ACK, 0, payload, seq)
    
    metrics.log_packet_sent()
    send_log.append({
        'timestamp': time.time(),
        'msg_type': 'INIT_ACK',
        'dest_addr': str(addr),
        'snapshot_id': 0,
        'payload_size': len(payload)
    })

# --- Event processing ---
def process_event(sock, data, addr):
    try:
        ts, r, c = struct.unpack("!Q H H", data[:12])
    except:
        return
    
    with lock:
        if addr in clients:
            clients[addr].packet_count_received += 1
            clients[addr].last_seen = time.time()
        event_queue.append((addr, r, c, ts))
        metrics.log_event()
        
    event_log.append({
        'timestamp': time.time(),
        'player_id': clients[addr].player_id if addr in clients else 0,
        'row': r,
        'col': c
    })

def apply_events():
    with lock:
        while event_queue:
            addr, r, c, ts = event_queue.popleft()
            if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
                # Only claim if empty
                if grid[r][c] == 0 and addr in clients:
                    grid[r][c] = clients[addr].player_id

def check_game_over():
    """Check if game is over (all cells claimed)"""
    with lock:
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if grid[r][c] == 0:
                    return False
        return True

def calculate_scores():
    """Calculate score for each player"""
    scores = Counter()
    with lock:
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if grid[r][c] != 0:
                    scores[grid[r][c]] += 1
    return scores

def broadcast_game_over(sock):
    """Broadcast game over message with scores"""
    global game_over
    
    scores = calculate_scores()
    scoreboard = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # Create payload
    n_players = len(scoreboard)
    payload = struct.pack("!B", n_players)
    for pid, score in scoreboard:
        payload += struct.pack("!B H", pid, score)
    
    # Log results
    log_message("\n" + "="*60)
    log_message("GAME OVER!")
    log_message("="*60)
    log_message("Final Scores:")
    for pid, score in scoreboard:
        log_message(f"  Player {pid}: {score} cells")
    if scoreboard:
        log_message(f"\nWinner: Player {scoreboard[0][0]} with {scoreboard[0][1]} cells!")
    log_message("="*60 + "\n")
    
    # Broadcast to all clients (with redundancy)
    with lock:
        for addr in clients.keys():
            # Send multiple times for reliability
            for _ in range(3):
                seq = int(time.time() * 1000) & 0xffffffff
                server_utils.send_packet(sock, addr, MSG_GAME_OVER, 0, payload, seq)
                metrics.log_packet_sent()
                time.sleep(0.01)  # Small delay between redundant sends
            
            send_log.append({
                'timestamp': time.time(),
                'msg_type': 'GAME_OVER',
                'dest_addr': str(addr),
                'snapshot_id': 0,
                'payload_size': len(payload)
            })
    
    game_over = True

# --- Snapshot broadcasting with redundancy ---
def broadcast_snapshots(sock):
    global snapshot_id, game_over
    interval = 1.0 / SNAPSHOT_RATE_HZ
    
    while running and not game_over:
        start = time.time()
        apply_events()
        
        # Sample CPU periodically
        if snapshot_id % 10 == 0:
            metrics.sample_cpu()



        with lock:
            snapshot_id += 1
            metrics.log_snapshot()
            
            # Pack grid into bytes
            flat_grid = bytes([grid[r][c] for r in range(GRID_SIZE) for c in range(GRID_SIZE)])
            payload = struct.pack("!B I Q H", 1, snapshot_id, server_utils.current_time_ms(), GRID_SIZE*GRID_SIZE)
            payload += flat_grid

            # Send to each client with optional redundancy
            for addr, client_state in clients.items():
                # Update client state
                client_state.last_sent_snapshot = snapshot_id
                client_state.pending_snapshots.append(snapshot_id)
                client_state.packet_count_sent += 1
                
                seq = int(time.time() * 1000) & 0xffffffff
                
                # Primary send
                server_utils.send_packet(sock, addr, MSG_SNAPSHOT, snapshot_id, payload, seq)
                metrics.log_packet_sent()
                
                # Optional redundancy: resend recent snapshots
                if RETRANSMIT_K > 1:
                    # Resend last K-1 snapshots for reliability
                    for old_sid in list(client_state.pending_snapshots)[-RETRANSMIT_K:-1]:
                        if old_sid > client_state.last_ack_snapshot:
                            # Resend this old snapshot
                            server_utils.send_packet(sock, addr, MSG_SNAPSHOT, old_sid, payload, seq)
                            metrics.log_packet_sent()
                
                # Log the send
                if snapshot_id % 20 == 0:  # Log every 20th snapshot to reduce overhead
                    send_log.append({
                        'timestamp': time.time(),
                        'msg_type': 'SNAPSHOT',
                        'dest_addr': str(addr),
                        'snapshot_id': snapshot_id,
                        'payload_size': len(payload)
                    })

        elapsed = time.time() - start
        time.sleep(max(0, interval - elapsed))
        
        # IMPORTANT: Give clients time to receive and render the final snapshot
        # Check game over AFTER sending the snapshot, and add a small grace period
        if check_game_over():
            log_message("[SERVER] All cells claimed! Sending final snapshot one more time...")
            # Send final snapshot once more to ensure all clients have it
            time.sleep(0.1)  # 100ms grace period
            with lock:
                for addr, client_state in clients.items():
                    seq = int(time.time() * 1000) & 0xffffffff
                    server_utils.send_packet(sock, addr, MSG_SNAPSHOT, snapshot_id, payload, seq)
            time.sleep(0.1)  # Another 100ms for clients to render
            log_message("[SERVER] Game is over.")
            broadcast_game_over(sock)
            break
    
    # After game over, wait for clients to receive message
    if game_over:
        log_message("[SERVER] Waiting 5 seconds for clients to receive game over message...")
        time.sleep(5)
        
        # Print final statistics
        stats = metrics.get_stats()
        log_message("\n" + "="*60)
        log_message("SERVER PERFORMANCE STATISTICS")
        log_message("="*60)
        log_message(f"Uptime: {stats['uptime_seconds']:.1f} seconds")
        log_message(f"Total Snapshots: {stats['total_snapshots']}")
        log_message(f"Total Events: {stats['total_events']}")
        log_message(f"Packets Sent: {stats['packets_sent']}")
        log_message(f"Packets Received: {stats['packets_received']}")
        log_message(f"Snapshot Rate: {stats['snapshot_rate']:.2f} Hz")
        log_message(f"Average CPU: {stats['avg_cpu']:.1f}%")
        log_message(f"Max CPU: {stats['max_cpu']:.1f}%")
        log_message("="*60 + "\n")
        
        # Save logs
        save_logs()

# --- Handle ACKs (optional but recommended) ---
def handle_ack(data, addr):
    """Handle acknowledgment from client"""
    try:
        ack_snapshot_id = struct.unpack("!I", data[:4])[0]
        with lock:
            if addr in clients:
                client_state = clients[addr]
                client_state.last_ack_snapshot = max(client_state.last_ack_snapshot, ack_snapshot_id)
                # Remove acknowledged snapshots from pending queue
                client_state.pending_snapshots = deque(
                    [sid for sid in client_state.pending_snapshots if sid > ack_snapshot_id],
                    maxlen=10
                )
    except:
        pass

# --- Main server loop ---
def server_loop():
    global running
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 9999))
    sock.settimeout(0.05)
    log_message(f"[SERVER] Listening on 0.0.0.0:9999")
    log_message(f"[SERVER] Snapshot rate: {SNAPSHOT_RATE_HZ} Hz")
    log_message(f"[SERVER] Redundancy factor: {RETRANSMIT_K}")
    log_message(f"[SERVER] Max clients: {MAX_CLIENTS}")

    # Start snapshot thread
    snapshot_thread = threading.Thread(target=broadcast_snapshots, args=(sock,), daemon=True)
    snapshot_thread.start()

    try:
        while running:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                metrics.log_packet_recv()
            except socket.timeout:
                continue
            
            parsed = None
            if len(data) >= HEADER_SIZE:
                parsed = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
            if not parsed:
                continue

            msg_type = parsed[2]
            payload = data[HEADER_SIZE:]
            
            # Log received message
            recv_log.append({
                'timestamp': time.time(),
                'msg_type': msg_type,
                'src_addr': str(addr),
                'payload_size': len(payload)
            })

            if msg_type == MSG_INIT:
                handle_init(sock, payload, addr)
            elif msg_type == MSG_EVENT:
                process_event(sock, payload, addr)
            elif msg_type == MSG_ACK:
                handle_ack(payload, addr)
            elif msg_type == MSG_GAME_OVER:
                log_message("[SERVER] Game over received from client")

    except KeyboardInterrupt:
        log_message("\n[SERVER] Shutting down")
        running = False
        save_logs()

    sock.close()

if __name__ == "__main__":
    server_loop()