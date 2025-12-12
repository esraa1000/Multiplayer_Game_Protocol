#!/usr/bin/env python3
"""
Test script to check if game over messages are being sent/received
"""

import socket
import struct
import time
from protocol_constants import *
from client_utils import parse_and_validate_header

SERVER_ADDR = ("127.0.0.1", 9999)

def monitor_messages():
    """Monitor all messages from server to see if GAME_OVER is sent"""
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    
    print("="*60)
    print("MONITORING SERVER MESSAGES")
    print("="*60)
    print(f"\nListening on port {sock.getsockname()[1]}...")
    print("Waiting for messages...\n")
    
    # Try to connect first
    nonce = int(time.time() * 1000)
    client_name = b"TestClient\x00\x00\x00\x00\x00\x00"
    payload = struct.pack("!Q16s", nonce, client_name)
    seq = int(time.time() * 1000) & 0xffffffff
    
    # Send INIT
    header = struct.pack("!B B H I Q", MSG_INIT, 0, len(payload), seq, 0)
    sock.sendto(header + payload, SERVER_ADDR)
    print("Sent INIT message to server")
    
    sock.settimeout(1.0)
    message_count = 0
    game_over_received = False
    
    try:
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                message_count += 1
                
                parsed = parse_and_validate_header(data)
                if parsed:
                    msg_type = parsed['msg_type']
                    
                    if msg_type == MSG_INIT_ACK:
                        print(f"✓ Received INIT_ACK")
                    elif msg_type == MSG_SNAPSHOT:
                        if message_count % 20 == 0:
                            print(f"  Received {message_count} snapshots...")
                    elif msg_type == MSG_GAME_OVER:
                        game_over_received = True
                        print(f"\n{'='*60}")
                        print("✓ GAME_OVER MESSAGE RECEIVED!")
                        print(f"{'='*60}")
                        print(f"Payload length: {len(parsed['payload'])} bytes")
                        print(f"Payload (hex): {parsed['payload'].hex()}")
                        
                        # Try to parse it
                        try:
                            payload = parsed['payload']
                            if len(payload) > 0:
                                n = payload[0]
                                print(f"\nNumber of players: {n}")
                                
                                p = 1
                                for i in range(n):
                                    if p + 3 <= len(payload):
                                        pid = payload[p]
                                        score = struct.unpack("!H", payload[p+1:p+3])[0]
                                        print(f"  Player {pid}: {score} cells")
                                        p += 3
                        except Exception as e:
                            print(f"Error parsing payload: {e}")
                        
                        break
                    else:
                        print(f"  Unknown message type: {msg_type}")
                        
            except socket.timeout:
                continue
                
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    
    if not game_over_received:
        print(f"\n{'='*60}")
        print("⚠️  NO GAME_OVER MESSAGE RECEIVED")
        print(f"{'='*60}")
        print(f"Total messages received: {message_count}")
        print("\nPossible issues:")
        print("  1. Server never sends MSG_GAME_OVER")
        print("  2. Game doesn't end (no win condition)")
        print("  3. Server sends it with wrong format")
        print("\nCheck your game_server.py for:")
        print("  - When does it send MSG_GAME_OVER?")
        print("  - What triggers the game end condition?")
        print("  - Is the payload format correct?")
    
    sock.close()

if __name__ == "__main__":
    print("\nThis tool monitors messages from the server")
    print("to check if GAME_OVER is being sent.\n")
    print("Make sure game_server.py is running!\n")
    
    input("Press Enter to start monitoring...")
    
    monitor_messages()