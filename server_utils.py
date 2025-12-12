# server_utils.py
import struct
import binascii
import time
from protocol_constants import HEADER_FMT, HEADER_SIZE, PROTO_ID, VERSION

def current_time_ms():
    return int(time.time() * 1000)

def crc32(data: bytes) -> int:
    return binascii.crc32(data) & 0xffffffff

def build_header(msg_type:int, snapshot_id:int, seq_num:int, server_ts_ms:int, payload_len:int, checksum:int=0) -> bytes:
    return struct.pack(HEADER_FMT, PROTO_ID, VERSION, msg_type, snapshot_id, seq_num, server_ts_ms, payload_len, checksum)

def send_packet(sock, addr, msg_type:int, snapshot_id:int, payload:bytes, seq_num:int):
    """
    Build RFC header, compute CRC32 over header-with-zero-checksum + payload,
    then send via UDP socket.
    """
    server_ts = current_time_ms()
    payload_len = len(payload)
    header_zero = build_header(msg_type, snapshot_id, seq_num, server_ts, payload_len, 0)
    checksum = crc32(header_zero + payload)
    header = build_header(msg_type, snapshot_id, seq_num, server_ts, payload_len, checksum)
    packet = header + payload
    sock.sendto(packet, addr)
    return True