#!/bin/bash

# Multiplayer Game Protocol - Automated Test Suite (Fixed: proper shutdown + more time)
# Runs all test scenarios and collects metrics into a single CSV per scenario

IF=lo
RESULTS_DIR=results
mkdir -p $RESULTS_DIR

NUM_CLIENTS=3
TEST_DURATION=30  # seconds per scenario
SHUTDOWN_GRACE=5  # extra seconds for graceful shutdown

# Function to run a single test scenario
run_test() {
    local scenario=$1
    local netem_cmd=$2

    echo ""
    echo "================================================"
    echo "Running scenario: $scenario"
    echo "================================================"

    # Clear any existing network rules
    sudo tc qdisc del dev $IF root 2>/dev/null || true

    # Apply network impairment if specified
    if [ ! -z "$netem_cmd" ]; then
        lo_cmd="${netem_cmd//eth0/$IF}"
        echo "Applying network impairment: $lo_cmd"
        eval $lo_cmd
        echo "Current network rules:"
        sudo tc qdisc show dev $IF
    fi

    # Clean up old log files
    rm -f server_send_log.csv server_recv_log.csv server_event_log.csv \
          server_positions.csv client_positions.csv 2>/dev/null || true

    # Start the game server
    python3 game_server.py &
    SERVER_PID=$!
    echo "Server started with PID $SERVER_PID"

    # Wait for server to initialize
    sleep 4

    # Start multiple headless clients
    CLIENT_PIDS=()
    OUTPUT_FILES=()
    for i in $(seq 1 $NUM_CLIENTS); do
        OUTPUT_CSV="$RESULTS_DIR/client_${i}_${scenario}.csv"
        python3 headless_client.py --duration $TEST_DURATION --scenario "$scenario" \
            --output_csv "$OUTPUT_CSV" --server_pid $SERVER_PID &
        CLIENT_PIDS+=($!)
        OUTPUT_FILES+=("$OUTPUT_CSV")
        echo "Started client $i with PID ${CLIENT_PIDS[-1]}"
        sleep 0.5  # stagger client starts slightly
    done

    # Wait for test duration + grace period
    echo "Running test for ${TEST_DURATION}s..."
    sleep $TEST_DURATION
    
    echo "Waiting ${SHUTDOWN_GRACE}s for graceful shutdown..."
    sleep $SHUTDOWN_GRACE

    # Send SIGTERM for graceful shutdown first
    echo "Sending graceful shutdown signals..."
    for pid in "${CLIENT_PIDS[@]}"; do
        kill -TERM $pid 2>/dev/null || true
    done
    
    # Wait a bit for graceful shutdown
    sleep 2
    
    # Force kill any remaining clients
    for pid in "${CLIENT_PIDS[@]}"; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "Force killing client $pid"
            kill -9 $pid 2>/dev/null || true
        fi
    done

    # Stop server gracefully
    kill -TERM $SERVER_PID 2>/dev/null || true
    sleep 1
    kill -9 $SERVER_PID 2>/dev/null || true

    # Merge all client CSVs into a single file per scenario
    MERGED_CSV="$RESULTS_DIR/client_metrics_${scenario}.csv"
    echo "Merging client CSVs into $MERGED_CSV..."
    first_file=1
    merged_count=0
    
    for f in "${OUTPUT_FILES[@]}"; do
        if [ -f "$f" ]; then
            if [ $first_file -eq 1 ]; then
                # write header
                cat "$f" > "$MERGED_CSV"
                first_file=0
                echo "  - Started merge with $f"
            else
                # skip header, append rows
                tail -n +2 "$f" >> "$MERGED_CSV"
                echo "  - Appended $f"
            fi
            merged_count=$((merged_count + 1))
        else
            echo "  - WARNING: $f not found"
        fi
    done
    
    echo "Merged $merged_count client files"

    # Save server logs
    [ -f server_send_log.csv ] && cp server_send_log.csv $RESULTS_DIR/server_send_${scenario}.csv
    [ -f server_recv_log.csv ] && cp server_recv_log.csv $RESULTS_DIR/server_recv_${scenario}.csv
    [ -f server_event_log.csv ] && cp server_event_log.csv $RESULTS_DIR/server_event_${scenario}.csv
    [ -f server_positions.csv ] && cp server_positions.csv $RESULTS_DIR/server_positions_${scenario}.csv

    # Clear network rules
    sudo tc qdisc del dev $IF root 2>/dev/null || true

    # Count collected metrics
    if [ -f "$MERGED_CSV" ]; then
        metric_count=$(($(wc -l < "$MERGED_CSV") - 1))
        echo "Collected $metric_count metrics for $scenario"
        
        # Show a sample of the data
        if [ $metric_count -gt 0 ]; then
            echo "Sample metrics:"
            head -n 3 "$MERGED_CSV"
        fi
    else
        echo "WARNING: No metrics file created for $scenario"
    fi

    echo "Completed $scenario test"
    echo ""
}

# Define test scenarios
declare -A scenarios
scenarios["baseline"]=""
scenarios["loss2"]="sudo tc qdisc add dev $IF root netem loss 2%"
scenarios["loss5"]="sudo tc qdisc add dev $IF root netem loss 5%"
scenarios["delay100"]="sudo tc qdisc add dev $IF root netem delay 100ms"

# Ask for sudo upfront
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

# Run all scenarios
for key in baseline loss2 loss5 delay100; do
    run_test "$key" "${scenarios[$key]}"
    sleep 3  # pause between scenarios
done

# Final cleanup
sudo tc qdisc del dev $IF root 2>/dev/null || true

# Summary
echo ""
echo "================================================"
echo "TEST SUMMARY"
echo "================================================"
echo "All tests completed! Results saved in: $RESULTS_DIR/"
echo ""
for key in baseline loss2 loss5 delay100; do
    csv_file="$RESULTS_DIR/client_metrics_${key}.csv"
    if [ -f "$csv_file" ]; then
        metric_count=$(($(wc -l < "$csv_file") - 1))
        echo "Scenario $key: $metric_count metrics"
    else
        echo "Scenario $key: NO DATA"
    fi
done
echo ""

# Check for any individual client files that weren't merged
echo "Individual client files:"
ls -lh $RESULTS_DIR/client_*_*.csv 2>/dev/null || echo "  (none found)"
echo ""