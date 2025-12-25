## **Description**

This prototype demonstrates **INIT** and **DATA** message exchanges using a custom **UDP-based protocol** for the Mini-RFC.
It verifies that the client and server can communicate correctly and exchange structured messages under the specified constraints.



## **Requirements**

* **Python 3.8+**
* **Linux / WSL environment** (for bash script execution)
* No external libraries required (uses `socket` and `struct`)

---

## **How to Run Locally**

### **Step 1 – Make the Script Executable**

If running for the first time:

```bash
chmod +x run_all_tests.sh
```

### **Step 2 – Run Automated Baseline Test**

Execute:

```bash
./run_all_tests.sh
```

The script will:

1. Start the server in the background
2. Run the client to send INIT and DATA messages
3. Log all packet exchanges to `logs/`
4. Print test summary results to the console

Expected output example:

```
Running scenario: baseline
Server running on port 9999...
Received msg_type=1 seq=1 payload_len=1 from ('127.0.0.1', 40251)
Sent INIT_ACK to ('127.0.0.1', 40251) with seq=1
Metrics collected and saved to ./results/baseline.csv
Test for baseline completed
--------------------------------
All tests completed successfully.
```
### **Step 3 – Analyze and Verify Results**

After the automated tests finish, use the provided scripts to process the data, verify requirements, and generate visual plots.

**1. Generate Statistics**
Calculates mean latency, throughput, and error rates from the CSV logs.
```bash
python3 generate_statistics.py
```

**2. Verify Requirements**
Checks if the results pass the project's acceptance criteria (e.g., Latency ≤ 50ms, Error ≤ 0.5).
```
# Make executable if needed
chmod +x verify_requirements

# Run verification
./verify_requirements
```

**3. Generate Plots**
Creates graphs for latency, jitter, and packet loss in t

```
python3 generate_plots.py
```

## **Manual Run (Optional)**

If you want to test manually without the script:

In one terminal:

```bash
python server.py
```

In another terminal:
```
python3 headless_client.py
```
#### Specific Test Scenarios (Manual)

To manually reproduce the specific network conditions (Loss/Delay) from the requirements, use the commands below.

#### Important :
You must run the clean up command after each test, or your computer's network will remain slow!

##### 1. Loss 2% (LAN-like)
Simulates minor packet loss.

```
# 1. Apply Network Rule
sudo tc qdisc add dev lo root netem loss 2%

# 2. Run Test
python3 game_server.py & python3 headless_client.py

# 3. Clean Up (Reset Network)
sudo tc qdisc del dev lo root
```
##### 2. Loss 5% (WAN-like)
Simulates heavy packet loss.

```
# 1. Apply Network Rule
sudo tc qdisc add dev lo root netem loss 5%

# 2. Run Test
python3 game_server.py & python3 headless_client.py

# 3. Clean Up
sudo tc qdisc del dev lo root
```
##### 3. Delay 100ms (WAN Latency)
Simulates high latency.

```
# 1. Apply Network Rule
sudo tc qdisc add dev lo root netem delay 100ms

# 2. Run Test
python3 game_server.py & python3 headless_client.py

# 3. Clean Up
sudo tc qdisc del dev lo root
```


## **Demo Video Link**
https://engasuedu-my.sharepoint.com/:v:/g/personal/23p0386_eng_asu_edu_eg/IQD-o_mzSZTCQpiUzCPUpAKZATyHJuseioi1n_F2GuvouPQ?e=tyWr2s&nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJTdHJlYW1XZWJBcHAiLCJyZWZlcnJhbFZpZXciOiJTaGFyZURpYWxvZy1MaW5rIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXcifX0%3D
