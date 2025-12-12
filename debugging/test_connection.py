#!/usr/bin/env python3
"""
Simple connection test to debug why GUI client can't connect
"""

import socket
import struct
import time
import sys

SERVER_ADDR = ("127.0.0.1", 9999)

# Try to import protocol constants
try:
    from protocol_constants import *
    from client_utils import current_time_ms, parse_and_validate_header
    import server_utils
    print("✓ Protocol modules imported successfully")
except ImportError as e:
    print(f"✗ Failed to import modules: {e}")
    print("  Make sure protocol_constants.py, client_utils.py, and server_utils.py exist")
    sys.exit(1)

def test_connection():
    """Test basic connection to server"""
    
    print(f"\n{'='*60}")
    print("TESTING CONNECTION TO GAME SERVER")
    print(f"{'='*60}\n")
    
    # Step 1: Create socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        local_port = sock.getsockname()[1]
        print(f"✓ Socket created and bound to port {local_port}")
    except Exception as e:
        print(f"✗ Failed to create socket: {e}")
        return False
    
    # Step 2: Check if server port is reachable
    print(f"\nAttempting to connect to {SERVER_ADDR[0]}:{SERVER_ADDR[1]}...")
    
    # Step 3: Send INIT message
    try:
        nonce = current_time_ms()
        payload = struct.pack("!Q16s", nonce, b"TestClient")
        seq = int(time.time() * 1000) & 0xffffffff
        
        print(f"  Sending INIT message (nonce={nonce}, seq={seq})...")
        server_utils.send_packet(sock, SERVER_ADDR, MSG_INIT, 0, payload, seq)
        print(f"  ✓ INIT message sent")
        
    except Exception as e:
        print(f"  ✗ Failed to send INIT: {e}")
        sock.close()
        return False
    
    # Step 4: Wait for INIT_ACK
    print(f"  Waiting for INIT_ACK response...")
    
    for attempt in range(5):
        try:
            sock.settimeout(1.0)
            data, addr = sock.recvfrom(4096)
            
            print(f"  ✓ Received {len(data)} bytes from {addr}")
            
            # Try to parse it
            parsed = parse_and_validate_header(data)
            if parsed:
                print(f"  Message type: {parsed['msg_type']}")
                
                if parsed['msg_type'] == MSG_INIT_ACK:
                    print(f"  ✓ Received INIT_ACK!")
                    
                    # Parse player ID from payload
                    if len(parsed['payload']) >= 24:
                        client_nonce, player_id, _, _ = struct.unpack('!Q I I Q', parsed['payload'][:24])
                        
                        if client_nonce == nonce:
                            print(f"  ✓ Nonce matches!")
                            print(f"  ✓ Assigned Player ID: {player_id}")
                            print(f"\n{'='*60}")
                            print("✓ CONNECTION SUCCESSFUL!")
                            print(f"{'='*60}\n")
                            print("The server is working correctly.")
                            print("The issue is likely in gui_client.py")
                            sock.close()
                            return True
                        else:
                            print(f"  ✗ Nonce mismatch: sent {nonce}, received {client_nonce}")
                else:
                    print(f"  ✗ Unexpected message type: {parsed['msg_type']} (expected {MSG_INIT_ACK})")
            else:
                print(f"  ✗ Failed to parse message header")
            
        except socket.timeout:
            print(f"  Attempt {attempt + 1}/5: No response (timeout)")
            if attempt < 4:
                print(f"  Retrying...")
                # Resend INIT
                try:
                    server_utils.send_packet(sock, SERVER_ADDR, MSG_INIT, 0, payload, seq)
                except:
                    pass
        except Exception as e:
            print(f"  ✗ Error receiving: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print(f"\n{'='*60}")
    print("✗ CONNECTION FAILED")
    print(f"{'='*60}\n")
    print("Possible issues:")
    print("  1. Game server is not running")
    print("     Solution: Run 'python3 game_server.py' in another terminal")
    print("  2. Server is running on a different port")
    print("     Solution: Check SERVER_ADDR in protocol_constants.py")
    print("  3. Firewall blocking connection")
    print("     Solution: Check firewall rules for localhost")
    print("  4. Server crashed or not responding")
    print("     Solution: Check server terminal for error messages")
    print("  5. Protocol mismatch between client and server")
    print("     Solution: Make sure both are using same version of protocol files")
    
    sock.close()
    return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("CONNECTION DIAGNOSTIC TOOL")
    print("="*60)
    print("\nThis will test the connection to the game server")
    print("Make sure game_server.py is running in another terminal!\n")
    
    # First check if required files exist
    import os
    required_files = ['protocol_constants.py', 'client_utils.py', 'server_utils.py', 'game_server.py', 'gui_client.py']
    
    print("Checking required files:")
    all_exist = True
    for filename in required_files:
        exists = os.path.exists(filename)
        status = "✓" if exists else "✗"
        print(f"  {status} {filename}")
        if not exists:
            all_exist = False
    
    if not all_exist:
        print("\n✗ Some required files are missing!")
        sys.exit(1)
    
    print()
    
    # Run the connection test
    success = test_connection()
    
    if success:
        print("\nYou can now try running:")
        print("  python3 gui_client.py")
        sys.exit(0)
    else:
        print("\nPlease fix the connection issues before running gui_client.py")
        sys.exit(1)