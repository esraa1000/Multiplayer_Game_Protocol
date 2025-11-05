import socket
import struct
import time 
import zlib #for checksum

HEADER_FORMAT = "!4s B B I I Q H I"  # protocol_id, version, msg_type, snapshot_id, seq_num,server_timestamp, payload_len, checksum
PROTOCOL_ID = b"CCLP"  # ChronoClash Protocol
VERSION = 1

HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Message type constants
MSG_INIT = 0x01
MSG_INIT_ACK = 0x02
MSG_SNAPSHOT = 0x03
MSG_EVENT = 0x04
MSG_ACK = 0x05
MSG_GAME_OVER = 0x06

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(("0.0.0.0", 9999))

print("Server running on port 9999...")

seq_counter = 0

while True:
    data, addr = server_socket.recvfrom(2048)
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
        checksum
    ) = struct.unpack(HEADER_FORMAT, header)


    if protocol_id != PROTOCOL_ID:
            print("Invalid protocol, ignoring packet.")
            continue
    print(f"Received msg_type={msg_type} seq={seq_num} payload_len={payload_len} from {addr}")

    if msg_type == MSG_INIT:
        response_payload = b"INIT_ACK"
        seq_counter += 1
        snapshot_id = 0

        temp_header = struct.pack(
            HEADER_FORMAT,
            PROTOCOL_ID,
            VERSION,
            MSG_INIT_ACK,
            snapshot_id,
            seq_counter,
            int(time.time() * 1000),
            len(response_payload),
            0
        )
        checksum = zlib.crc32(temp_header + response_payload) & 0xFFFFFFFF
        response_header = struct.pack(
            HEADER_FORMAT,
            PROTOCOL_ID,
            VERSION,
            MSG_INIT_ACK,
            snapshot_id,
            seq_counter,
            int(time.time() * 1000),
            len(response_payload),
            checksum
        )

        server_socket.sendto(response_header + response_payload, addr)
        print(f"Sent INIT_ACK to {addr} with seq={seq_counter}")

        
