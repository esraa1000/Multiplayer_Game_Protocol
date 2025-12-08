import socket
import threading 

from protocol_constants import *
from server_utils import (
    parse_and_validate_header,
    send_packet,
    current_time_ms
)
from game_server import (
    register_new_player,
    queue_event,
    snapshot_loop,
    process_pending_events,
    broadcast_snapshot,
    broadcast_game_over,
    GRID_SIZE,
    SNAPSHOT_RATE_HZ,
    REDUNDANCY_K 
)


server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(("0.0.0.0", 9999))

print("Server running on port 9999...")

snapshot_thread = threading.Thread(target=snapshot_loop, args=(server_socket,), daemon=True)
snapshot_thread.start()

while True:
    data, addr = server_socket.recvfrom(2048)

    parsed = parse_and_validate_header(data)
    if parsed is None:
        print("[WARN] Invalid packet, ignoring...")
        continue

    msg_type = parsed["msg_type"]
    snapshot_id = parsed["snapshot_id"]
    seq_num = parsed["seq_num"]
    payload = parsed["payload"]

    print(f"[RECV] type={msg_type} seq={seq_num} from {addr}")

   # INIT handler
    if msg_type == MSG_INIT:
        if len(payload) >= 4:
            client_nonce = struct.unpack('!I', payload[:4])[0]
            player_name = payload[4:].decode('utf-8', errors='ignore')[:32]
            player_id = register_new_player(addr, player_name)
            
            # INIT_ACK payload: nonce(4), player_id(1), snapshot_id(4), server_time(8)
            response_payload = struct.pack('!IBIQ', client_nonce, player_id, 0, current_time_ms())
            send_packet(server_socket, addr, MSG_INIT_ACK, 0, response_payload)
            print(f"[INFO] Sent INIT_ACK (P{player_id}) to {addr}")
    
    # EVENT handler
    elif msg_type == MSG_EVENT:
        if len(payload) == 11:
            player_id, row, col, timestamp = struct.unpack('!BBBQ', payload)
            queue_event(player_id, "ACQUIRE_REQUEST", row, col, timestamp)
            print(f"[EVENT] P{player_id} ({row},{col})")

    # Unknown types
    else:
        print(f"[WARN] Unknown msg_type={msg_type}")