#!/bin/bash
# run_all_tests.sh

IF=lo  
RESULTS_DIR="./results"

mkdir -p $RESULTS_DIR

run_test() {
  scenario=$1
  netem_cmd=$2
  echo "Running scenario: $scenario"

  # Clear old netem config
  sudo tc qdisc del dev $IF root 2>/dev/null

  if [ ! -z "$netem_cmd" ]; then
    echo "Applying netem: $netem_cmd"
    sudo tc qdisc add dev $IF root netem $netem_cmd
  fi

  python3 server.py &
  SERVER_PID=$!
  sleep 1
  python3 client.py --duration 10 --scenario "$scenario" > "$RESULTS_DIR/${scenario}.log"
  kill $SERVER_PID

  # save metrics
  python3 collect_metrics.py "$RESULTS_DIR/${scenario}.log" "$RESULTS_DIR/${scenario}.csv"

  echo "Test for $scenario completed"
  echo "--------------------------------"
}

# Baseline test
run_test "baseline" ""

#will add other test later

sudo tc qdisc del dev $IF root 2>/dev/null

# log file
echo "All tests completed successfully."