# gui_client.py (Fixed: Connection + Smooth Interpolation + Interactive Clicks)
import threading
import socket
import struct
import time
import tkinter as tk
from tkinter import messagebox

from protocol_constants import *
from client_utils import parse_and_validate_header, parse_snapshot_payload, current_time_ms
import server_utils   # for send_packet

# Configuration
SERVER_ADDR = ("127.0.0.1", 9999)
GRID_SIZE = 5
CELL_SIZE = 80
SMOOTHING_FPS = 60               # interpolation update rate
SMOOTHING_DURATION = 0.12        # 120 ms smoothing per snapshot
SNAPSHOT_RATE = 20               # must match server-side
RETRANSMIT_INTERVAL = 1.0 / SNAPSHOT_RATE
last_sent_ts = current_time_ms()
# Runtime state
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

player_id = None
running = True
last_snapshot_id = -1   # accept first snapshot with id >= 0

# For smoothing:
current_grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
target_grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
transition_start_time = None     # timestamp when smoothing started

# Reliable EVENT tracking:
pending_events = {}   # (row,col)-> {sent_ts, retries}

# Player Colors (RGB tuples) — interpolation expects numeric tuples
PLAYER_COLORS = [
    (255, 255, 255),   # 0 white
    (255, 179, 186),   # 1 pastel pink
    (186, 225, 255),   # 2 pastel blue
    (186, 255, 201),   # 3 pastel green
    (255, 223, 186),   # 4 pastel orange
]

def rgb_to_hex(rgb):
    """Convert an (r,g,b) tuple to a Tk-compatible hex string."""
    return "#%02x%02x%02x" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))

# INIT handshake - FIXED
def connect():
    global player_id
    nonce = current_time_ms()
    # FIX: Pad to exactly 16 bytes
    client_name = b"GUI_Player\x00\x00\x00\x00\x00\x00"  # 10 chars + 6 nulls = 16 bytes
    payload = struct.pack("!Q16s", nonce, client_name)

    seq = int(time.time()*1000) & 0xffffffff
    server_utils.send_packet(sock, SERVER_ADDR, MSG_INIT, 0, payload, seq)

    sock.settimeout(5.0)
    try:
        data, _ = sock.recvfrom(4096)
    except Exception as e:
        print(f"[GUI] Connection timeout: {e}")
        return False

    parsed = parse_and_validate_header(data)
    if not parsed or parsed["msg_type"] != MSG_INIT_ACK:
        print(f"[GUI] Invalid response or wrong message type")
        return False

    try:
        client_nonce, pid, _, _ = struct.unpack("!Q I I Q", parsed["payload"][:24])
        if client_nonce != nonce:
            print(f"[GUI] Nonce mismatch")
            return False
        player_id = pid
        print(f"[GUI] Connected as Player {player_id}")
        return True
    except Exception as e:
        print(f"[GUI] Error parsing INIT_ACK: {e}")
        return False


# EVENT sending - User clicks to claim cells
def send_move(row, col):
     
    global last_sent_ts

    now=current_time_ms()
    delta = now - last_sent_ts

    if delta<0:
        delta=0
    if delta > 65535:
        delta=65535
    last_sent_ts = now

    if player_id is None:
        return

    payload = struct.pack("!H H H", delta, row, col)
    seq = int(time.time()*1000) & 0xffffffff
    server_utils.send_packet(sock, SERVER_ADDR, MSG_EVENT, 0, payload, seq)

    pending_events[(row,col)] = {'sent_ts': current_time_ms(), 'retries': 0}


# RECEIVE THREAD
def recv_thread(canvas, root):
    global last_snapshot_id, target_grid, current_grid
    global transition_start_time, running

    sock.settimeout(0.1)

    while running:
        try:
            data, _ = sock.recvfrom(4096)
        except:
            continue

        parsed = parse_and_validate_header(data)
        if not parsed:
            continue

        msg_type = parsed['msg_type']
        if msg_type == MSG_SNAPSHOT:
            snap = parse_snapshot_payload(parsed['payload'], GRID_SIZE)
            if not snap:
                continue

            sid = snap["snapshot_id"]

            # Reject outdated snapshots
            if sid <= last_snapshot_id:
                continue

            last_snapshot_id = sid

            # New grid becomes target for smoothing (deep copy to avoid shared refs)
            # ensure we copy ints (not references)
            tg = [[int(cell) for cell in row] for row in snap["grid"]]
            target_grid = tg
            # start transition from the CURRENT displayed state to the TARGET
            transition_start_time = time.time()

            # Clear pending events if resolved
            resolve_pending_events()

        elif msg_type == MSG_GAME_OVER:
            show_game_over(parsed["payload"], root)
            running = False


# EVENT RELIABILITY (Retransmission)
def retransmit_loop():
    while running:
        time.sleep(RETRANSMIT_INTERVAL)
        for (r,c), info in list(pending_events.items()):
            if info['retries'] >= 10:
                pending_events.pop((r,c), None)
                continue

            # Retransmit
            payload = struct.pack("!Q H H", current_time_ms(), r, c)
            seq = int(time.time()*1000) & 0xffffffff
            server_utils.send_packet(sock, SERVER_ADDR, MSG_EVENT, 0, payload, seq)

            info['retries'] += 1
            info['sent_ts'] = current_time_ms()


def resolve_pending_events():
    """Remove pending EVENTs that are already reflected in the target grid."""
    for (r,c), info in list(pending_events.items()):
        # guard against early calls before target_grid is set
        try:
            if target_grid[r][c] != 0:
                pending_events.pop((r,c), None)
        except Exception:
            continue


# INTERPOLATION / SMOOTHING LOOP
def smoothing_loop(canvas):
    global transition_start_time, current_grid, target_grid, running

    while running:
        time.sleep(1.0 / SMOOTHING_FPS)

        # If no transition in progress
        if transition_start_time is None:
            continue

        t = (time.time() - transition_start_time) / SMOOTHING_DURATION

        if t >= 1:
            # End of interpolation -> snap to target (deep copy ints)
            copy_grid(target_grid, current_grid)
            transition_start_time = None
        else:
            # Blend between old and new
            interpolate_grids(current_grid, target_grid, t)

        # update GUI
        try:
            update_canvas(canvas)
        except:
            pass


def copy_grid(src, dst):
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            dst[r][c] = int(src[r][c])


def interpolate_grids(cur, tgt, alpha):
    """
    Alpha-blend between current integer grid and target integer grid.
    cur is modified in place.

    Behaviour:
    - If cell owner unchanged -> keep int owner
    - If changing -> compute blended RGB between owner colors and store RGB tuple temporarily.
    - When alpha >= 1 the cur cell is set to the integer owner from tgt.
    """
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            src = cur[r][c]
            dst = tgt[r][c]

            # both should be ints (or src might be a temporary tuple)
            # If already equal and src is int, nothing to do
            if isinstance(src, int) and src == dst:
                continue

            # get color tuple for current state
            if isinstance(src, tuple):
                c1 = src
            else:
                # src expected to be int; fallback to 0 if invalid
                idx1 = src if isinstance(src, int) and 0 <= src < len(PLAYER_COLORS) else 0
                c1 = PLAYER_COLORS[idx1]

            # get color tuple for target
            if isinstance(dst, tuple):
                c2 = dst
            else:
                idx2 = dst if isinstance(dst, int) and 0 <= dst < len(PLAYER_COLORS) else 0
                c2 = PLAYER_COLORS[idx2]

            # compute blended color
            rcol = (
                int(c1[0] + (c2[0] - c1[0]) * alpha),
                int(c1[1] + (c2[1] - c1[1]) * alpha),
                int(c1[2] + (c2[2] - c1[2]) * alpha),
            )

            if alpha >= 1:
                # finalize to integer owner (from target)
                cur[r][c] = int(dst)
            else:
                # temporary interpolated RGB
                cur[r][c] = rcol


# GUI UPDATE
def update_canvas(canvas):
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            owner = current_grid[r][c]

            if isinstance(owner, tuple):
                # interpolated RGB value
                color = rgb_to_hex(owner)
            else:
                idx = owner if isinstance(owner, int) and 0 <= owner < len(PLAYER_COLORS) else 0
                color = rgb_to_hex(PLAYER_COLORS[idx])

            canvas.itemconfig(rects[r][c], fill=color)


# GAME OVER POPUP
def show_game_over(payload, root):
    try:
        n = payload[0]
        p = 1
        scoreboard = []
        for _ in range(n):
            pid = payload[p]
            score = struct.unpack("!H", payload[p+1:p+3])[0]
            scoreboard.append((pid, score))
            p += 3
    except:
        scoreboard = []

    def popup():
        msg = "Game Over!\n\n" + "\n".join([f"Player {pid}: {score} cells" for pid, score in scoreboard])
        if scoreboard:
            winner = max(scoreboard, key=lambda x: x[1])
            if winner[0] == player_id:
                msg = f"🎉 You Won! 🎉\n\n{msg}"
            else:
                msg = f"Winner: Player {winner[0]}\n\n{msg}"
        messagebox.showinfo("Game Over", msg)

    root.after(0, popup)


# MOUSE CLICK HANDLER - User clicks to claim cells
def on_click(event):
    r = event.y // CELL_SIZE
    c = event.x // CELL_SIZE
    if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
        # Only send if cell is empty
        if target_grid[r][c] == 0:
            send_move(r, c)
            print(f"[GUI] Player {player_id} clicked cell ({r}, {c})")


# MAIN
if __name__ == "__main__":
    print("="*60)
    print("CHRONOCLASH - Multiplayer Grid Game")
    print("="*60)
    print()
    
    if not connect():
        print("[GUI] Could not connect to server")
        print("\nMake sure game_server.py is running!")
        exit(1)

    root = tk.Tk()
    root.title(f"ChronoClash - Player {player_id}")

    canvas = tk.Canvas(root, width=GRID_SIZE * CELL_SIZE, height=GRID_SIZE * CELL_SIZE)
    canvas.pack()

    # Rectangle references
    global rects
    rects = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
            rects[r][c] = canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="black")

    canvas.bind("<Button-1>", on_click)

    # Start background threads
    threading.Thread(target=recv_thread, args=(canvas, root), daemon=True).start()
    threading.Thread(target=retransmit_loop, daemon=True).start()
    threading.Thread(target=smoothing_loop, args=(canvas,), daemon=True).start()

    print(f"\n✓ Connected as Player {player_id}")
    print("Click on empty cells to claim them!")
    print()

    root.mainloop()
    running = False
    sock.close()
    print("\n[GUI] Game closed")