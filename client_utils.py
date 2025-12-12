# client_utils.py
import struct
import binascii
import time
from protocol_constants import HEADER_FMT, HEADER_SIZE, PROTO_ID, VERSION, MAX_PACKET_BYTES

def current_time_ms():
    return int(time.time() * 1000)

def crc32(data: bytes) -> int:
    return binascii.crc32(data) & 0xffffffff

def parse_and_validate_header(raw: bytes):
    """
    Validates length, proto_id, CRC32 and returns dict:
    {
      'proto_id': b'CCLP', 'version': int, 'msg_type': int,
      'snapshot_id': int, 'seq_num': int, 'server_ts': int,
      'payload_len': int, 'checksum': int, 'payload': bytes
    }
    Returns None if invalid.
    """
    if len(raw) < HEADER_SIZE:
        return None
    header = raw[:HEADER_SIZE]
    payload = raw[HEADER_SIZE:]
    try:
        proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, checksum = struct.unpack(HEADER_FMT, header)
    except Exception:
        return None
    if proto_id != PROTO_ID or version != VERSION:
        return None
    # verify payload length vs advertised
    if payload_len != len(payload):
        # allow shorter/longer during dev, but reject
        return None
    # verify CRC
    header_zero = struct.pack(HEADER_FMT, proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, 0)
    if crc32(header_zero + payload) != checksum:
        return None
    return {
        'proto_id': proto_id,
        'version': version,
        'msg_type': msg_type,
        'snapshot_id': snapshot_id,
        'seq_num': seq_num,
        'server_ts': server_ts,
        'payload_len': payload_len,
        'checksum': checksum,
        'payload': payload
    }

def parse_snapshot_payload(payload: bytes, grid_size:int):
    """
    Snapshot payload format (we use exactly the server build format):
      1 byte: num_snapshots (N)
      For each snapshot:
        4 bytes snapshot_id (I)
        8 bytes timestamp_ms (Q)
        2 bytes grid_len (H)
        grid_len bytes of grid (each cell 0..255)
        (optional: scoreboard or flags are ignored by client display)
    Return latest snapshot dict:
      {'snapshot_id': int, 'server_ts': int, 'grid': [[...]]}
    Returns None if parse fails.
    """
    try:
        if len(payload) < 1:
            return None
        p = 0
        num_snaps = payload[p]
        p += 1
        latest = None
        for _ in range(num_snaps):
            if p + 14 > len(payload):
                break
            sid = struct.unpack('!I', payload[p:p+4])[0]; p += 4
            stime = struct.unpack('!Q', payload[p:p+8])[0]; p += 8
            glen = struct.unpack('!H', payload[p:p+2])[0]; p += 2
            if p + glen > len(payload):
                break
            grid_bytes = payload[p:p+glen]; p += glen
            # convert to n x n grid if length matches
            if glen == grid_size * grid_size:
                flat = list(grid_bytes)
                grid = [flat[i*grid_size:(i+1)*grid_size] for i in range(grid_size)]
            else:
                # incompatible grid size; skip
                grid = None
            if latest is None or sid > latest['snapshot_id']:
                latest = {'snapshot_id': sid, 'server_ts': stime, 'grid': grid}
        return latest
    except Exception:
        return None