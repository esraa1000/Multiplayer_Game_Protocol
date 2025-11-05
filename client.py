import socket
import struct
import time
import zlib

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

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_addr = ("127.0.0.1", 9999)

seq_num = 1
payload = b"\x01"  # client_id = 1
snapshot_id = 0

temp_header = struct.pack(
    HEADER_FORMAT,
    PROTOCOL_ID,
    VERSION,
    MSG_INIT,
    snapshot_id,
    seq_num,
    int(time.time() * 1000),  
    len(payload),
    0
)

checksum = zlib.crc32(temp_header + payload)

header = struct.pack(
    HEADER_FORMAT,
    PROTOCOL_ID,
    VERSION,
    MSG_INIT,
    snapshot_id,
    seq_num,
    int(time.time() * 1000),
    len(payload),
    checksum
)

packet = header + payload
client_socket.sendto(packet, server_addr)

print("INIT sent")

data, _ = client_socket.recvfrom(2048)
recv_header = data[:HEADER_SIZE]
recv_payload = data[HEADER_SIZE:]

(
    protocol_id,
    version,
    msg_type,
    snapshot_id,
    seq_num,
    server_timestamp,
    payload_len,
    checksum
) = struct.unpack(HEADER_FORMAT, recv_header)

if protocol_id != PROTOCOL_ID:
    print("Invalid protocol in response.")
else:
    print(f"Received msg_type={msg_type} seq={seq_num} payload={recv_payload.decode(errors='ignore')}")