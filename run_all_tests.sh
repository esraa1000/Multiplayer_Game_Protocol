#!/bin/bash

# ===============================================================
# Multiplayer Game Protocol - Automated Test Suite
# Cleaned Output Version (Professional, Readable, Structured)
# ===============================================================

IF=lo
RESULTS_DIR=results
mkdir -p $RESULTS_DIR

NUM_CLIENTS=3
TEST_DURATION=30
SHUTDOWN_GRACE=5

# ---------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------
divider() { 
    printf "\n\e[1;34m================================================\e[0m\n"; 
}

section() {
    printf "\e[1;33m==> %s\e[0m\n" "$1"
}

subsection() {
    printf "   \e[1;36m- %s\e[0m\n" "$1"
}

success() {
    printf "   \e[1;32m✔ %s\e[0m\n" "$1"
}

warn() {
    printf "   \e[1;31m⚠ %s\e[0m\n" "$1"
}

note() {
    printf "   \e[0;35m• %s\e[0m\n" "$1"
}

# ---------------------------------------------------------------
# Run a single scenario
# ---------------------------------------------------------------
run_test() {
    local scenario=$1
    local netem_cmd=$2

    divider
    section "Running scenario: $scenario"
    divider

    # Clear old qdisc
    sudo tc qdisc del dev $IF root 2>/dev/null || true

    # Apply impairment
    if [ ! -z "$netem_cmd" ]; then
        lo_cmd="${netem_cmd//eth0/$IF}"
        subsection "Applying network impairment:"
        note "$lo_cmd"
        eval $lo_cmd
        note "Active qdisc:"
        sudo tc qdisc show dev $IF
    else
        subsection "No network impairment (baseline)"
    fi

    # Clean logs
    rm -f server_send_log.csv server_recv_log.csv server_event_log.csv \
          server_positions.csv client_positions.csv 2>/dev/null || true

    # Start server
    section "Starting server"
    python3 game_server.py &
    SERVER_PID=$!
    success "Server PID = $SERVER_PID"
    sleep 3

    # Start clients
    section "Starting clients ($NUM_CLIENTS)"
    CLIENT_PIDS=()
    OUTPUT_FILES=()

    for i in $(seq 1 $NUM_CLIENTS); do
        CSV="$RESULTS_DIR/client_${i}_${scenario}.csv"
        python3 headless_client.py --duration $TEST_DURATION --scenario "$scenario" \
            --output_csv "$CSV" --server_pid $SERVER_PID &

        CLIENT_PIDS+=($!)
        OUTPUT_FILES+=("$CSV")
        success "Client $i PID = ${CLIENT_PIDS[-1]}"
        sleep 0.4
    done

    section "Running simulation for $TEST_DURATION seconds..."
    sleep $TEST_DURATION

    subsection "Waiting $SHUTDOWN_GRACE seconds for graceful shutdown..."
    sleep $SHUTDOWN_GRACE

    # Shutdown clients
    section "Stopping clients"
    for pid in "${CLIENT_PIDS[@]}"; do
        kill -TERM $pid 2>/dev/null || true
    done
    sleep 2

    for pid in "${CLIENT_PIDS[@]}"; do
        if ps -p $pid >/dev/null 2>&1; then
            warn "Client $pid still alive, force-killing"
            kill -9 $pid 2>/dev/null || true
        else
            success "Client $pid exited cleanly"
        fi
    done

    # Stop server
    section "Stopping server"
    kill -TERM $SERVER_PID 2>/dev/null || true
    sleep 1
    kill -9 $SERVER_PID 2>/dev/null || true
    success "Server shutdown complete"

    # Merge CSVs
    divider
    section "Merging metrics: $scenario"
    MERGED="$RESULTS_DIR/client_metrics_${scenario}.csv"

    first=1
    count=0

    for f in "${OUTPUT_FILES[@]}"; do
        if [ -f "$f" ]; then
            if [ $first -eq 1 ]; then
                cp "$f" "$MERGED"
                subsection "Created master CSV from $f"
                first=0
            else
                tail -n +2 "$f" >> "$MERGED"
                subsection "Merged $f"
            fi
            count=$((count + 1))
        else
            warn "$f missing!"
        fi
    done

    success "Merged $count client CSV files"

    # Copy server logs
    [ -f server_send_log.csv ] && cp server_send_log.csv $RESULTS_DIR/server_send_${scenario}.csv
    [ -f server_recv_log.csv ] && cp server_recv_log.csv $RESULTS_DIR/server_recv_${scenario}.csv
    [ -f server_event_log.csv ] && cp server_event_log.csv $RESULTS_DIR/server_event_${scenario}.csv
    [ -f server_positions.csv ] && cp server_positions.csv $RESULTS_DIR/server_positions_${scenario}.csv

    # Reset qdisc
    sudo tc qdisc del dev $IF root 2>/dev/null || true

    # Metrics summary
    if [ -f "$MERGED" ]; then
        total=$(($(wc -l < "$MERGED") - 1))
        section "Collected $total metrics for scenario: $scenario"

        note "Sample:"
        head -n 3 "$MERGED"
    else
        warn "Merged metrics not found!"
    fi

    success "Completed scenario: $scenario"
}

# ---------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------
declare -A scenarios=(
    ["baseline"]=""
    ["loss2"]="sudo tc qdisc add dev $IF root netem loss 2%"
    ["loss5"]="sudo tc qdisc add dev $IF root netem loss 5%"
    ["delay100"]="sudo tc qdisc add dev $IF root netem delay 100ms"
)

# Sudo refresh
sudo -v

# ---------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------
for s in baseline loss2 loss5 delay100; do
    run_test "$s" "${scenarios[$s]}"
    sleep 2
done

# ---------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------
divider
section "TEST SUMMARY"
divider

echo "Results saved in: $RESULTS_DIR/"
echo ""

for s in baseline loss2 loss5 delay100; do
    FILE="$RESULTS_DIR/client_metrics_${s}.csv"
    if [ -f "$FILE" ]; then
        total=$(($(wc -l < "$FILE") - 1))
        printf "  %-12s : %s metrics\n" "$s" "$total"
    else
        printf "  %-12s : NO DATA\n" "$s"
    fi
done

echo ""
section "Individual Client Files:"
ls -lh $RESULTS_DIR/client_*_*.csv 2>/dev/null || echo "  (none found)"
echo ""
