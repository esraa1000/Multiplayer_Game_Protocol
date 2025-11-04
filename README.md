## **Description**

This prototype demonstrates **INIT** and **DATA** message exchanges using a custom **UDP-based protocol** for the Mini-RFC assignment.
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
[SERVER] Listening on 127.0.0.1:9999
[CLIENT] INIT sent
[CLIENT] DATA sent: "Hello, Server!"
[SERVER] Received DATA from client
[SERVER] Sent ACK
[TEST] Baseline run complete – PASS
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
```
