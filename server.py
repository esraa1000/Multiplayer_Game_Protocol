import socket

from protocol_constants import *
from server_utils import (
    parse_and_validate_header,
    send_packet
)

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(("0.0.0.0", 9999))

print("Server running on port 9999...")

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
        response_payload = b"INIT_ACK"
        send_packet(server_socket, addr, MSG_INIT_ACK, snapshot_id, response_payload)
        print(f"[INFO] Sent INIT_ACK to {addr}")