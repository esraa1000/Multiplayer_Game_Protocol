# gui_client.py
import threading
import socket
import struct
import time
import tkinter as tk
from tkinter import messagebox

from protocol_constants import *
from client_utils import parse_and_validate_header, parse_snapshot_payload, current_time_ms
from client_utils import crc32

SERVER_ADDR = ("127.0.0.1", 9999)  

GRID_SIZE = 5
CELL_SIZE = 80

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
player_id = None
latest_grid = None
running = True
pending_events = {}   # (row,col) -> {'sent_ts','retries'}
retransmit_interval = 0.25

# colors for up to 4 players
PLAYER_COLORS = [
    "#ffffff",   # 0 = empty
    "#ffb3ba",
    "#bae1ff",
    "#baffc9",
    "#ffdfba",
]

# INIT handshake: send INIT and wait for INIT_ACK
def connect():
    global player_id
    nonce = current_time_ms()
    payload = struct.pack('!Q', nonce) + b'GUI_Player'
    # build header and send manually using server_utils.send_packet interface
    import server_utils
    seq_num = int(time.time()*1000) & 0xffffffff
    server_utils.send_packet(sock, SERVER_ADDR, MSG_INIT, 0, payload, seq_num)
    sock.settimeout(5.0)
    try:
        data, _ = sock.recvfrom(4096)
    except Exception:
        return False
    parsed = parse_and_validate_header(data)
    if not parsed or parsed['msg_type'] != MSG_INIT_ACK:
        return False
    # parse payload: client_nonce (Q) player_id (I) initial_snapshot (I) server_ts (Q)
    try:
        client_nonce, pid, initial_snapshot, server_ts = struct.unpack('!Q I I Q', parsed['payload'][:24])
        player_id = pid
        print(f"[GUI] Connected as player {player_id}")
    except Exception as e:
        print("INIT_ACK parse err", e)
        return False
    return True

def send_move(row, col):
    if player_id is None:
        return
    payload = struct.pack('!Q H H', current_time_ms(), row, col)
    import server_utils
    seq_num = int(time.time()*1000) & 0xffffffff
    server_utils.send_packet(sock, SERVER_ADDR, MSG_EVENT, 0, payload, seq_num)
    # record pending
    pending_events[(row,col)] = {'sent_ts': current_time_ms(), 'retries': 0}

def recv_thread(canvas, root):
    global latest_grid, running
    sock.settimeout(0.1)
    while running:
        try:
            data, _ = sock.recvfrom(4096)
        except:
            continue
        parsed = parse_and_validate_header(data)
        if not parsed:
            continue
        if parsed['msg_type'] == MSG_SNAPSHOT:
            snap = parse_snapshot_payload(parsed['payload'], GRID_SIZE)
            if snap and snap.get('grid') is not None:
                # accept only if newer
                latest_grid = snap['grid']
                # remove any pending_events that are now resolved
                resolved = []
                for (r,c), info in list(pending_events.items()):
                    if latest_grid[r][c] != 0:
                        resolved.append((r,c))
                for k in resolved:
                    pending_events.pop(k, None)
                # update canvas in main thread
                try:
                    root.after(0, update_canvas, canvas)
                except:
                    pass
        elif parsed['msg_type'] == MSG_GAME_OVER:
            # extract scoreboard
            data = parsed['payload']
            try:
                n = data[0]; p = 1
                scoreboard = []
                for _ in range(n):
                    pid = data[p]; score = struct.unpack('!H', data[p+1:p+3])[0]; p += 3
                    scoreboard.append((pid, score))
            except:
                scoreboard = []
            def show_game_over():
                msg = "Game Over!\n" + "\n".join([f"P{pid}: {score}" for pid, score in scoreboard])
                messagebox.showinfo("Game Over", msg)
            root.after(0, show_game_over)
            running = False

def retransmit_loop():
    while running:
        time.sleep(retransmit_interval)
        for (r,c), info in list(pending_events.items()):
            # if exceeded retries remove
            if info['retries'] >= 10:
                pending_events.pop((r,c), None)
                continue
            # retransmit
            payload = struct.pack('!Q H H', current_time_ms(), r, c)
            import server_utils
            seq_num = int(time.time()*1000) & 0xffffffff
            server_utils.send_packet(sock, SERVER_ADDR, MSG_EVENT, 0, payload, seq_num)
            info['retries'] += 1
            info['sent_ts'] = current_time_ms()

def update_canvas(canvas):
    if latest_grid is None:
        return
    grid = latest_grid
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            owner = grid[r][c]
            color = PLAYER_COLORS[owner] if 0 <= owner < len(PLAYER_COLORS) else "#cccccc"
            canvas.itemconfig(rects[r][c], fill=color)

def on_click(event):
    r = event.y // CELL_SIZE
    c = event.x // CELL_SIZE
    if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
        send_move(r, c)

if __name__ == "__main__":
    if not connect():
        print("[GUI] Could not connect")
        exit(1)

    root = tk.Tk()
    root.title(f"ChronoClash - Player {player_id}")

    canvas = tk.Canvas(root, width=GRID_SIZE*CELL_SIZE, height=GRID_SIZE*CELL_SIZE)
    canvas.pack()

    rects = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            x1, y1 = c*CELL_SIZE, r*CELL_SIZE
            x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
            rects[r][c] = canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="black")

    canvas.bind("<Button-1>", on_click)

    threading.Thread(target=recv_thread, args=(canvas, root), daemon=True).start()
    threading.Thread(target=retransmit_loop, daemon=True).start()

    root.mainloop()
    running = False
    sock.close()
