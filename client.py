import socket
import struct
import time
import threading
from protocol_constants import *
from client_utils import *

# Global state
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_addr = ("127.0.0.1", 9999)
player_id = None
latest_grid = None
running = True
metrics = MetricsLogger()

def connect():
    """Send INIT and get player ID."""
    global player_id
    #number used once 
    nonce = int(time.time() * 1000) & 0xFFFFFFFF
    payload = struct.pack('!I', nonce) + b"Player1"
    send_packet(sock, server_addr, MSG_INIT, 0, payload)
    
    sock.settimeout(5.0)
    data, _ = sock.recvfrom(2048)
    parsed = parse_and_validate_header(data)
    if parsed and parsed["msg_type"] == MSG_INIT_ACK:
        _, player_id, _, _ = struct.unpack('!IBIQ', parsed["payload"][:17])
        print(f"[CLIENT] Connected as Player {player_id}")
        return True
    return False

def receive_loop():
    """Background thread - receive and log packets."""
    global latest_grid, running
    sock.settimeout(0.1)
    
    while running:
        try:
            data, _ = sock.recvfrom(2048)
            parsed = parse_and_validate_header(data)
            if not parsed:
                continue
            
           
            metrics.log(player_id, parsed["snapshot_id"], parsed["seq_num"], 
                       parsed["server_timestamp"], current_time_ms())
            
            
            if parsed["msg_type"] == MSG_SNAPSHOT:
                snap = parse_snapshot_payload(parsed["payload"])
                if snap:
                    latest_grid = snap
                    print(f"[CLIENT] Snapshot {parsed['snapshot_id']} received")
            
          
            elif parsed["msg_type"] == MSG_GAME_OVER:
                print("[CLIENT] Game Over!")
                running = False
        except:
            continue

def send_move(row, col):
    """Send acquire request for a cell."""
    payload = struct.pack('!BBBQ', player_id, row, col, current_time_ms())
    send_packet(sock, server_addr, MSG_EVENT, 0, payload)
    print(f"[CLIENT] Sent move: ({row}, {col})")

# this function will be deleted after the game UI is built
def display_grid():
    """Display current grid and scores."""
    if latest_grid:
        print("\n[CLIENT] Current Grid:")
        for row in latest_grid['grid']:
            print("  ", row)
        print("[CLIENT] Scores:", latest_grid['scores'])
        if latest_grid.get('game_over'):
            print("[CLIENT] Game is over!")
        print()
    else:
        print("[CLIENT] No grid received yet")

# This section will be deleted after the game UI is built (should be replaced by event loop in GUI)
if __name__ == "__main__":
    if not connect():
        print("[CLIENT] Connection failed")
        exit(1)
    
    # Start receiver
    threading.Thread(target=receive_loop, daemon=True).start()
    print("[CLIENT] Waiting for snapshots...")
    time.sleep(1)
    
    # Send some moves
    print("\n[CLIENT] Sending moves...")
    send_move(0, 0)
    time.sleep(0.5)
    send_move(1, 1)
    time.sleep(0.5)
    send_move(2, 2)
    time.sleep(1)
    
    # Display grid
    display_grid()
    
    # Wait for game over
    print("[CLIENT] Running... Press Ctrl+C to stop")
    try:
        while running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[CLIENT] Stopping...")
    
    sock.close()
    print("[CLIENT] Disconnected")
