import threading
import socket
import tkinter as tk
from tkinter import messagebox
import struct
import time

from protocol_constants import *
from client_utils import (
    send_packet,
    parse_and_validate_header,
    parse_snapshot_payload,
    current_time_ms
)

# Server address
SERVER_ADDR = (" 105.180.167.15", 9999)

GRID_SIZE = 5
CELL_SIZE = 80

running = True
player_id = None
latest_grid = None

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


# ====== PASTEL COLORS FOR EXACTLY 4 PLAYERS ======
PLAYER_COLORS = [
    "#ffffff",   # 0 = empty (white)

    "#ffb3ba",   # Player 1 = pastel pink
    "#bae1ff",   # Player 2 = pastel blue
    "#baffc9",   # Player 3 = pastel green
    "#ffdfba",   # Player 4 = pastel orange
]
# ================================================


# INIT HANDSHAKE
def connect():
    global player_id

    nonce = int(time.time() * 1000) & 0xFFFFFFFF
    payload = struct.pack("!I", nonce) + b"GUI_Player"

    send_packet(sock, SERVER_ADDR, MSG_INIT, 0, payload)

    sock.settimeout(5)

    data, _ = sock.recvfrom(2048)
    parsed = parse_and_validate_header(data)

    if not parsed or parsed["msg_type"] != MSG_INIT_ACK:
        print("[GUI] INIT_ACK failed.")
        return False

    nonce_recv, pid, _, _ = struct.unpack("!IBIQ", parsed["payload"][:17])
    if nonce_recv != nonce:
        print("[GUI] Nonce mismatch, invalid INIT_ACK.")
        return False

    player_id = pid
    print(f"[GUI] Connected as Player {player_id}")
    return True

# EVENT: user clicks a cell
def send_move(row, col):
    payload = struct.pack("!BBBQ", player_id, row, col, current_time_ms())
    send_packet(sock, SERVER_ADDR, MSG_EVENT, 0, payload)

# RECEIVE LOOP
def receive_loop(canvas, root):
    global latest_grid, running
    sock.settimeout(0.1)

    while running:
        try:
            data, _ = sock.recvfrom(4096)
            parsed = parse_and_validate_header(data)

            if not parsed:
                continue

            if parsed["msg_type"] == MSG_SNAPSHOT:
                snap = parse_snapshot_payload(parsed["payload"])
                if snap:
                    latest_grid = snap
                    update_canvas(canvas)

            elif parsed["msg_type"] == MSG_GAME_OVER:
                print("[GUI] GAME OVER received.")
                running = False

                # ===== EXTRACT WINNER ID FROM PAYLOAD =====
                try:
                    winner_id = parsed["payload"][0]   # 1 byte winner ID
                except:
                    winner_id = None

                # ===== SHOW POPUP EXACTLY ONCE =====
                def show_game_over():
                    if winner_id is None:
                        msg = "The game has ended!"
                    else:
                        msg = f"Player {winner_id} has won the game!"
                    messagebox.showinfo("Game Over", msg)

                root.after(0, show_game_over)

        except:
            continue

# GUI UPDATE
def update_canvas(canvas):
    if not latest_grid:
        return

    grid = latest_grid["grid"]

    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            owner = grid[r][c]

            if 0 <= owner < len(PLAYER_COLORS):
                color = PLAYER_COLORS[owner]
            else:
                color = "#cccccc"   # fallback gray for invalid IDs

            canvas.itemconfig(rects[r][c], fill=color)


# Mouse click event
def on_click(event):
    r = event.y // CELL_SIZE
    c = event.x // CELL_SIZE
    if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
        send_move(r, c)

# MAIN
if __name__ == "__main__":
    if not connect():
        print("[GUI] Could not connect. Exiting.")
        exit()

    root = tk.Tk()
    root.title(f"ChronoClash - Player {player_id}")

    canvas = tk.Canvas(root, width=GRID_SIZE * CELL_SIZE, height=GRID_SIZE * CELL_SIZE)
    canvas.pack()

    rects = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
            rects[r][c] = canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="black")

    canvas.bind("<Button-1>", on_click)

    # root is passed safely
    threading.Thread(target=receive_loop, args=(canvas, root), daemon=True).start()

    root.mainloop()

    running = False
    sock.close()
