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

---

## **Manual Run (Optional)**

If you want to test manually without the script:

In one terminal:

```bash
python server.py
```

In another terminal:

```bash
python client.py
``