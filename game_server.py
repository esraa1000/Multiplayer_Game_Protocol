# game_server.py
import socket
import struct
import threading
import time
from collections import deque
from server_utils import send_packet, current_time_ms
from protocol_constants import MSG_INIT, MSG_INIT_ACK, MSG_SNAPSHOT, MSG_EVENT, MSG_GAME_OVER, MAX_PACKET_BYTES
from client_utils import crc32  # optional utility; server uses own if needed

# Configuration
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 9999
GRID_SIZE = 5
REDUNDANCY_K = 2
SNAPSHOT_RATE_HZ = 20

# Runtime state
snapshot_counter = 0
grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
players = {}           # player_id -> {"addr": (ip,port), "name": name, "last_snapshot_id": int}
addr_to_pid = {}       # (ip,port) -> player_id
next_player_id = 1
snapshot_history = deque(maxlen=REDUNDANCY_K)
pending_events = []    # list of (event_ts_ms, player_id, row, col, arrival_order)
arrival_seq = 0
game_over = False
player_scores = {}

# Logging CSV filenames
RECV_LOG = 'server_recv_log.csv'
SEND_LOG = 'server_send_log.csv'
EVENT_LOG = 'server_event_log.csv'

# Helper: pack single snapshot
def pack_single_snapshot(snapshot_id:int, server_ts:int, grid_state):
    # grid_state: flattened list of bytes length GRID_SIZE*GRID_SIZE
    grid_flat = [grid_state[r][c] for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    grid_bytes = struct.pack(f'!{GRID_SIZE*GRID_SIZE}B', *grid_flat)
    # minimal metadata: snapshot_id (I) + timestamp (Q) + grid_len (H) + grid_bytes
    return struct.pack('!I Q H', snapshot_id, server_ts, len(grid_bytes)) + grid_bytes

# Build payload containing up to K snapshots (newest-first)
def build_snapshot_payload():
    # snapshot_history stores tuples (snapshot_id, timestamp_ms, grid_flat_bytes)
    snaps = list(snapshot_history)[-REDUNDANCY_K:]
    payload_chunks = []
    for sid, stime, grid_flat_bytes in snaps:
        glen = len(grid_flat_bytes)
        payload_chunks.append(struct.pack('!I Q H', sid, stime, glen) + grid_flat_bytes)
    payload = struct.pack('!B', len(payload_chunks)) + b''.join(payload_chunks)
    if len(payload) > MAX_PACKET_BYTES:
        raise ValueError("Snapshot payload too large")
    return payload

# Apply acquire request server-authoritative
def apply_acquire_request(player_id:int, row:int, col:int):
    if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE and grid[row][col] == 0:
        grid[row][col] = player_id
        player_scores[player_id] = player_scores.get(player_id, 0) + 1
        return True
    return False

# Register new player (called when INIT received)
def register_new_player(addr, player_name):
    global next_player_id
    pid = next_player_id
    next_player_id += 1
    players[pid] = {"addr": addr, "name": player_name, "last_snapshot_id": 0}
    addr_to_pid[addr] = pid
    player_scores[pid] = 0
    print(f"[SERVER] New player {pid} from {addr} name={player_name}")
    return pid

# Process pending events in timestamp order
def process_pending_events():
    global pending_events
    if not pending_events:
        return
    # sort by (event_ts, arrival_order)
    pending_events.sort(key=lambda e: (e[0], e[4]))
    while pending_events:
        ev_ts, pid, row, col, arr = pending_events.pop(0)
        applied = apply_acquire_request(pid, row, col)
        # log
        with open(EVENT_LOG, 'a') as f:
            f.write(f"{current_time_ms()},{pid},{row},{col},{applied}\n")

# Networking: receive loop
def recv_loop(sock):
    global arrival_seq, game_over
    sock.settimeout(0.5)
    while not game_over:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        recv_t = current_time_ms()
        # validate header and CRC using client_utils.parse_and_validate_header semantics
        from client_utils import parse_and_validate_header
        parsed = parse_and_validate_header(data)
        if parsed is None:
            # invalid packet; ignore
            continue
        msg_type = parsed['msg_type']
        payload = parsed['payload']
        # log receive
        with open(RECV_LOG, 'a') as f:
            f.write(f"{recv_t},{addr},{hex(msg_type)},{parsed['seq_num']},{parsed['snapshot_id']}\n")
        if msg_type == MSG_INIT:
            # INIT payload: client_nonce (Q) + optionally name bytes
            try:
                if len(payload) >= 8:
                    client_nonce = struct.unpack('!Q', payload[:8])[0]
                    name = payload[8:].decode('utf-8', errors='ignore') if len(payload) > 8 else 'Player'
                else:
                    client_nonce = current_time_ms()
                    name = 'Player'
            except:
                client_nonce = current_time_ms(); name='Player'
            pid = register_new_player(addr, name)
            # send INIT_ACK payload: client_nonce (Q) + assigned pid (I) + initial_snapshot_id (I) + server_time(Q)
            initial_sid = snapshot_counter
            init_ack_payload = struct.pack('!Q I I Q', client_nonce, pid, initial_sid, current_time_ms())
            # use seq num from parsed for send index? use local counter
            send_packet(sock, addr, MSG_INIT_ACK, 0, init_ack_payload, seq_num=int(time.time()*1000) & 0xffffffff)
        elif msg_type == MSG_EVENT:
            # EVENT payload: event_ts_ms (Q) row (H) col (H)
            try:
                ev_ts, row, col = struct.unpack('!Q H H', payload[:12])
            except:
                ev_ts = current_time_ms(); row = col = 0
            # map addr to pid
            pid = addr_to_pid.get(addr)
            if pid is None:
                # ignore events from unknown clients
                continue
            arrival_seq += 1
            pending_events.append((ev_ts, pid, int(row), int(col), arrival_seq))
        else:
            # other messages ignored by server
            continue

# Snapshot broadcast loop
def snapshot_loop(sock):
    global snapshot_counter, game_over
    interval = 1.0 / SNAPSHOT_RATE_HZ
    while not game_over:
        process_pending_events()
        # build snapshot entry (snapshot_id, timestamp, grid_flat_bytes)
        snapshot_counter += 1
        sid = snapshot_counter
        stime = current_time_ms()
        flat = [grid[r][c] for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
        try:
            grid_flat_bytes = struct.pack(f'!{GRID_SIZE*GRID_SIZE}B', *flat)
        except Exception:
            # fallback: convert to bytes manually
            grid_flat_bytes = bytes([int(x) & 0xff for x in flat])
        snapshot_history.append((sid, stime, grid_flat_bytes))
        # build payload (up to K snapshots)
        payload = build_snapshot_payload()
        # broadcast to all players
        for pid, info in players.items():
            addr = info['addr']
            send_packet(sock, addr, MSG_SNAPSHOT, sid, payload, seq_num=int(time.time()*1000) & 0xffffffff)
            info['last_snapshot_id'] = sid
        # check game over
        empty_exists = any(cell == 0 for row in grid for cell in row)
        if not empty_exists:
            # broadcast game over
            scoreboard = sorted(player_scores.items(), key=lambda x: x[1], reverse=True)
            data = struct.pack('!B', len(scoreboard))
            for player_id, score in scoreboard:
                data += struct.pack('!BH', player_id, score)
            for pid, info in players.items():
                send_packet(sock, info['addr'], MSG_GAME_OVER, sid, data, seq_num=int(time.time()*1000) & 0xffffffff)
            game_over = True
            print("[SERVER] Game over. scoreboard:", scoreboard)
        time.sleep(interval)

def start_server(host=SERVER_HOST, port=SERVER_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"[SERVER] Listening on {host}:{port}")
    t_recv = threading.Thread(target=recv_loop, args=(sock,), daemon=True)
    t_snap = threading.Thread(target=snapshot_loop, args=(sock,), daemon=True)
    t_recv.start()
    t_snap.start()
    try:
        while not game_over:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[SERVER] shutting down")
    sock.close()

if __name__ == "__main__":
    # create/clear logs
    open(RECV_LOG, 'w').close()
    open(SEND_LOG, 'w').close()
    open(EVENT_LOG, 'w').close()
    start_server()
