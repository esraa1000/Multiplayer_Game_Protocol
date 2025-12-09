import threading
import socket
import tkinter as tk
import struct
import time

from protocol_constants import *
from client_utils import (
    send_packet,
    parse_and_validate_header,
    parse_snapshot_payload,
    current_time_ms
)
#el server address wl port betaato
SERVER_ADDR = ("127.0.0.1", 9999)

GRID_SIZE = 5
CELL_SIZE = 80

running = True
#hayakhod id baad el INIT
player_id = None
latest_grid = None

#baamel UDP socket lel communication
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)



# INIT HANDSHAKE

def connect():
    global player_id

    nonce = int(time.time() * 1000) & 0xFFFFFFFF
    #init payload
    payload = struct.pack("!I", nonce) + b"GUI_Player"


    #han send el init
    send_packet(sock, SERVER_ADDR, MSG_INIT, 0, payload)

    sock.settimeout(5)
    #hanestana el INIT_ACK
    data, _ = sock.recvfrom(2048)
    parsed = parse_and_validate_header(data)

    if not parsed or parsed["msg_type"] != MSG_INIT_ACK:
        print("[GUI] INIT_ACK failed.")
        return False

    # INIT_ACK payload = nonce(4), player_id(1), snapshot_id(4), server_time(8)
    #unpack el payload
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



# RECEIVE LOOP (runs in thread)

def receive_loop(canvas):
    global latest_grid, running
    sock.settimeout(0.1)

    while running:
        try:
            #receive packets
            data, _ = sock.recvfrom(4096)
            parsed = parse_and_validate_header(data)
            if not parsed:
                continue
            #handle el snapshot 
            if parsed["msg_type"] == MSG_SNAPSHOT:
                snap = parse_snapshot_payload(parsed["payload"])
                if snap:
                    latest_grid = snap
                    update_canvas(canvas)

            #game over
            elif parsed["msg_type"] == MSG_GAME_OVER:
                print("[GUI] GAME OVER received.")
                running = False

        except:
            continue



# GUI RELATED STUFF

def update_canvas(canvas):
    if not latest_grid:
        return

    grid = latest_grid["grid"]

    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            owner = grid[r][c]

        if owner == 0:
            color = "white"              # unclaimed
        elif owner == 1:
            color = "#ff9999"            # player 1 - soft red
        elif owner == 2:
            color = "#9999ff"            # player 2 - soft blue
        elif owner == 3:
            color = "#99ff99"            # player 3 - soft green
        elif owner == 4:
            color = "#ffcc99"            # player 4 - soft orange
        else:
            color = "gray"               # fallback for >4 players

        canvas.itemconfig(rects[r][c], fill=color)

#mouse click handler
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

    threading.Thread(target=receive_loop, args=(canvas,), daemon=True).start()

    root.mainloop()

    running = False
    sock.close()
