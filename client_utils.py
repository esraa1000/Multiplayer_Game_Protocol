import struct
import time
import zlib
import csv
from protocol_constants import (
    HEADER_FORMAT,
    HEADER_SIZE,
    PROTOCOL_ID,
    VERSION
)

# Client-side sequence counter
seq_counter = 0

def next_seq_num():
    global seq_counter
    seq_counter += 1
    return seq_counter

def current_time_ms():
    return int(time.time() * 1000)

def compute_crc32(header_without_crc, payload_bytes):
    return zlib.crc32(header_without_crc + payload_bytes) & 0xFFFFFFFF

def pack_header(msg_type, snapshot_id, seq_num, timestamp_ms, payload_bytes):
    payload_len = len(payload_bytes)
    
    temp_header = struct.pack(
        HEADER_FORMAT,
        PROTOCOL_ID,
        VERSION,
        msg_type,
        snapshot_id,
        seq_num,
        timestamp_ms,
        payload_len,
        0
    )
    
    crc = compute_crc32(temp_header, payload_bytes)
    
    final_header = struct.pack(
        HEADER_FORMAT,
        PROTOCOL_ID,
        VERSION,
        msg_type,
        snapshot_id,
        seq_num,
        timestamp_ms,
        payload_len,
        crc
    )
    return final_header

def parse_and_validate_header(data):
    if len(data) < HEADER_SIZE:
        return None
    
    header = data[:HEADER_SIZE]
    payload = data[HEADER_SIZE:]
    
    (
        protocol_id,
        version,
        msg_type,
        snapshot_id,
        seq_num,
        server_timestamp,
        payload_len,
        recv_checksum
    ) = struct.unpack(HEADER_FORMAT, header)
    
    if protocol_id != PROTOCOL_ID:
        return None
    if version != VERSION:
        return None
    if payload_len != len(payload):
        return None
    
    temp_header = struct.pack(
        HEADER_FORMAT,
        protocol_id,
        version,
        msg_type,
        snapshot_id,
        seq_num,
        server_timestamp,
        payload_len,
        0
    )
    computed = compute_crc32(temp_header, payload)
    if computed != recv_checksum:
        return None
    
    return {
        "msg_type": msg_type,
        "snapshot_id": snapshot_id,
        "seq_num": seq_num,
        "server_timestamp": server_timestamp,
        "payload": payload,
    }

def send_packet(sock, addr, msg_type, snapshot_id, payload_bytes):
    seq = next_seq_num()
    timestamp = current_time_ms()
    header = pack_header(msg_type, snapshot_id, seq, timestamp, payload_bytes)
    
    sock.sendto(header + payload_bytes, addr)
    print(f"[CLIENT SEND] type={msg_type} seq={seq}")

def parse_snapshot_payload(payload):
    """Parse snapshot payload into grid state and scores."""
    if len(payload) < 1:
        return None
    
    num_snapshots = struct.unpack('!B', payload[0:1])[0]
    snapshots = []
    offset = 1
    
    for _ in range(num_snapshots):
        if offset + 3 > len(payload):
            break
        
        grid_size = struct.unpack('!B', payload[offset:offset+1])[0]
        num_players = struct.unpack('!B', payload[offset+1:offset+2])[0]
        game_over = struct.unpack('!?', payload[offset+2:offset+3])[0]
        offset += 3
        
        grid_cells = grid_size * grid_size
        if offset + grid_cells > len(payload):
            break
        
        grid_data = struct.unpack(f'!{grid_cells}B', payload[offset:offset+grid_cells])
        grid = []
        for r in range(grid_size):
            row = list(grid_data[r*grid_size:(r+1)*grid_size])
            grid.append(row)
        offset += grid_cells
        
        scores = {}
        for _ in range(num_players):
            if offset + 3 > len(payload):
                break
            player_id, score_high, score_low = struct.unpack('!BBB', payload[offset:offset+3])
            scores[player_id] = (score_high << 8) | score_low
            offset += 3
        
        snapshots.append({
            "grid": grid,
            "scores": scores,
            "game_over": game_over,
            "grid_size": grid_size
        })
    
    return snapshots[0] if snapshots else None

class MetricsLogger:
    def __init__(self, filename="client_metrics.csv"):
        self.filename = filename
        with open(self.filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['client_id', 'snapshot_id', 'seq_num', 'server_timestamp', 'recv_time', 'latency_ms'])
    
    def log(self, client_id, snapshot_id, seq_num, server_timestamp, recv_time):
        latency = recv_time - server_timestamp
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([client_id, snapshot_id, seq_num, server_timestamp, recv_time, latency])
