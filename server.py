import socket
import struct

HEADER_FORMAT = "!4s B B I H"  # protocol_id, version, msg_type, seq_num, payload_len
PROTOCOL_ID = b"GCLH"
VERSION = 1
MSG_INIT = 0
MSG_DATA = 1

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(("0.0.0.0", 9999))

print("Server running on port 9999...")

seq_counter = 0

while True:
    data, addr = server_socket.recvfrom(2048)
    header = data[:12]
    protocol_id, version, msg_type, seq_num, payload_len = struct.unpack(HEADER_FORMAT, header)
    payload = data[12:12+payload_len]

    print(f"Received msg_type={msg_type} seq={seq_num} from {addr}")

    if msg_type == MSG_INIT:
        response_payload = b"ACK"
        seq_counter += 1
        response_header = struct.pack(
            HEADER_FORMAT,
            PROTOCOL_ID,
            VERSION,
            MSG_DATA,
            seq_counter,
            len(response_payload)
        )
        server_socket.sendto(response_header + response_payload, addr)
