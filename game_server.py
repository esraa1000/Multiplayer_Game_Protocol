# game_server.py
import time
import struct
import threading
from collections import deque
from server_utils import send_packet, current_time_ms
from protocol_constants import MSG_SNAPSHOT, MSG_GAME_OVER


GRID_SIZE = 5
REDUNDANCY_K = 2
SNAPSHOT_RATE_HZ = 30

snapshot_counter = 0 

grid = []
players = {}           # player_id -> {"addr": addr, "name": name, "last_snapshot_id": int}
next_player_id = 1
snapshot_history = deque(maxlen=REDUNDANCY_K)
pending_events = []
game_over = False
player_scores = {}  



def init_grid(size):
    return [ [0 for _ in range(size)] for _ in range(size) ]  

grid = init_grid(GRID_SIZE)

def register_new_player(addr, player_name):
    global next_player_id
    player_id = next_player_id
    next_player_id += 1
    players[player_id] = {"addr": addr, "name": player_name, "last_snapshot_id": 0}
    player_scores[player_id] = 0
    return player_id


def queue_event(player_id, event_type, row, col, timestamp_ms):
    pending_events.append({
        "player_id": player_id,
        "event_type": event_type,
        "row": row,
        "col": col,
        "timestamp_ms": timestamp_ms
    })

def process_pending_events():
    global pending_events
    for evt in pending_events:
        if evt["event_type"] == "ACQUIRE_REQUEST":
            apply_acquire_request(evt["player_id"], evt["row"], evt["col"])
    pending_events = []

def apply_acquire_request(player_id, row, col):
    if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE and grid[row][col] == 0:
        grid[row][col] = player_id
        player_scores[player_id] += 1
        return True
    return False


def build_snapshot():
    global snapshot_history
    # serialize current snapshot
    grid_flat = [grid[r][c] for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    grid_bytes = struct.pack(f'!{GRID_SIZE*GRID_SIZE}B', *grid_flat)

    scores_data = []
    for pid, score in player_scores.items():
        scores_data.extend([pid, (score >> 8) & 0xFF, score & 0xFF])

    single_snapshot = struct.pack('!BB?', GRID_SIZE, len(player_scores), game_over) + grid_bytes + bytes(scores_data)

    # build K snapshots with redundancy
    snapshots = [single_snapshot]
    for i in range(1, REDUNDANCY_K):
        if len(snapshot_history) >= i:
            snapshots.append(snapshot_history[-i])

    # update history
    snapshot_history.append(single_snapshot)
    

    packet = struct.pack('!B', len(snapshots)) + b''.join(snapshots)
    if len(packet) > 1200:
        raise ValueError(f"Snapshot packet too large: {len(packet)} bytes")

    return packet

def broadcast_snapshot(sock):
    global snapshot_counter
    snapshot_payload = build_snapshot()
    snapshot_counter += 1
    snapshot_id = snapshot_counter 
    for pid, info in players.items():
        send_packet(sock, info["addr"], MSG_SNAPSHOT, snapshot_id, snapshot_payload)
        info["last_snapshot_id"] = snapshot_id


def is_game_over():
    for row in grid:
        for cell in row:
            if cell == 0:
                return False
    return True

def compute_scoreboard():
    return sorted(player_scores.items(), key=lambda x: x[1], reverse=True)

def broadcast_game_over(sock):
    scoreboard = compute_scoreboard()
    data = struct.pack('!B', len(scoreboard))
    for player_id, score in scoreboard:
        data += struct.pack('!BH', player_id, score)
    for pid, info in players.items():
        send_packet(sock, info["addr"], MSG_GAME_OVER, 0, data)


def snapshot_loop(sock):
    global game_over
    interval = 1 / SNAPSHOT_RATE_HZ
    while not game_over:
        process_pending_events()
        broadcast_snapshot(sock)
        if is_game_over():
            broadcast_game_over(sock)
            game_over = True
            print("[INFO] Game over!")
        time.sleep(interval)
