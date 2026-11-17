import os, sys, time, json, urllib.request, subprocess, socket, base64, hashlib

def ws_handshake(sock, host, port, path):
    key = base64.b64encode(os.urandom(16)).decode('utf-8')
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(req.encode('utf-8'))
    resp = sock.recv(4096)
    if b"101 " not in resp:
        raise Exception("Handshake failed: " + resp.decode('utf-8', errors='ignore'))

def send_frame(sock, data_dict):
    payload = json.dumps(data_dict).encode('utf-8')
    length = len(payload)
    mask = os.urandom(4)
    masked_payload = bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))
    header = bytearray([0x81])
    if length <= 125:
        header.append(0x80 | length)
    elif length <= 65535:
        header.append(0x80 | 126)
        header.extend(length.to_bytes(2, 'big'))
    else:
        header.append(0x80 | 127)
        header.extend(length.to_bytes(8, 'big'))
    header.extend(mask)
    header.extend(masked_payload)
    sock.sendall(header)

def recv_frame(sock):
    header = sock.recv(2)
    if not header:
        return None
    length = header[1] & 0x7f
    if length == 126:
        length = int.from_bytes(sock.recv(2), 'big')
    elif length == 127:
        length = int.from_bytes(sock.recv(8), 'big')
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            break
        data += chunk
    return json.loads(data.decode('utf-8', errors='ignore'))

cmd = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    '--headless=new',
    '--remote-debugging-port=9555',
    '--user-data-dir=C:/Temp/chrome_test_p4',
    '--disable-gpu',
    'http://127.0.0.1:8080/'
]
proc = subprocess.Popen(cmd)
time.sleep(2.5)

try:
    with urllib.request.urlopen('http://127.0.0.1:9555/json') as r:
        tabs = json.loads(r.read().decode('utf-8'))
    page_tab = [t for t in tabs if '8080' in t.get('url', '')][0]
    ws_url = page_tab['webSocketDebuggerUrl']
    path = '/' + ws_url.split('/', 3)[3]
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 9555))
    ws_handshake(s, '127.0.0.1', 9555, path)

    # Enable console and runtime
    send_frame(s, {"id": 1, "method": "Runtime.enable"})
    send_frame(s, {"id": 2, "method": "Log.enable"})

    # Evaluate test expressions:
    # 1. Check window state
    send_frame(s, {"id": 3, "method": "Runtime.evaluate", "params": {"expression": "typeof switchTask"}})
    # 2. Try calling switchTask(2)
    send_frame(s, {"id": 4, "method": "Runtime.evaluate", "params": {"expression": "switchTask(2)"}})
    # 3. Check if panel 2 has active class
    send_frame(s, {"id": 5, "method": "Runtime.evaluate", "params": {"expression": "document.getElementById('panel-task-2').className"}})
    # 4. Try calling loadSampleDataset()
    send_frame(s, {"id": 6, "method": "Runtime.evaluate", "params": {"expression": "loadSampleDataset()"}})
    # 5. Check row count in task1
    send_frame(s, {"id": 7, "method": "Runtime.evaluate", "params": {"expression": "rawItems.length"}})

    s.settimeout(2.0)
    for _ in range(20):
        try:
            msg = recv_frame(s)
            if msg:
                print('CDP MSG:', json.dumps(msg, ensure_ascii=False)[:200])
        except socket.timeout:
            break
        if msg and 'method' in msg and msg['method'] == 'Runtime.exceptionThrown':
            print('FULL EXCEPTION DETAILS:')
            print(json.dumps(msg, indent=2, ensure_ascii=False))
finally:
    proc.terminate()
