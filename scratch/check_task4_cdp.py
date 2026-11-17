import os, sys, time, json, urllib.request, subprocess, socket, base64

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
    if length <= 125: header.append(0x80 | length)
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
    if not header: return None
    length = header[1] & 0x7f
    if length == 126: length = int.from_bytes(sock.recv(2), 'big')
    elif length == 127: length = int.from_bytes(sock.recv(8), 'big')
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk: break
        data += chunk
    return json.loads(data.decode('utf-8', errors='ignore'))

cmd = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    '--headless=new',
    '--remote-debugging-port=9888',
    '--user-data-dir=C:/Temp/chrome_test_p8',
    '--disable-gpu',
    'http://127.0.0.1:8080/'
]
proc = subprocess.Popen(cmd)
time.sleep(2.5)

try:
    with urllib.request.urlopen('http://127.0.0.1:9888/json') as r:
        tabs = json.loads(r.read().decode('utf-8'))
    page_tab = [t for t in tabs if '8080' in t.get('url', '')][0]
    ws_url = page_tab['webSocketDebuggerUrl']
    path = '/' + ws_url.split('/', 3)[3]
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 9888))
    ws_handshake(s, '127.0.0.1', 9888, path)

    send_frame(s, {"id": 1, "method": "Runtime.enable"})

    # 1. Gọi loadHungPhatSample()
    send_frame(s, {"id": 10, "method": "Runtime.evaluate", "params": {"expression": "loadHungPhatSample(); 'called'"}})
    time.sleep(2.0)

    # 2. Switch sang Task 4
    send_frame(s, {"id": 11, "method": "Runtime.evaluate", "params": {"expression": "switchTask(4); 'switched'"}})
    time.sleep(0.5)

    # 3. Đọc 5 giá trị KPI
    eval_kpis = """
    ({
        kpi1_lbl: document.getElementById('lbl-kpi-1').innerText,
        kpi1_val: document.getElementById('kpi-total-val').innerText,
        kpi2_lbl: document.getElementById('lbl-kpi-2').innerText,
        kpi2_val: document.getElementById('kpi-eligible').innerText,
        kpi3_lbl: document.getElementById('lbl-kpi-3').innerText,
        kpi3_val: document.getElementById('kpi-pending').innerText,
        kpi4_lbl: document.getElementById('lbl-kpi-4').innerText,
        kpi4_val: document.getElementById('kpi-dash-missing').innerText,
        kpi5_lbl: document.getElementById('lbl-kpi-5').innerText,
        kpi5_val: document.getElementById('kpi-unfeasible').innerText
    })
    """
    send_frame(s, {"id": 12, "method": "Runtime.evaluate", "params": {"expression": eval_kpis, "returnByValue": True}})

    s.settimeout(3.0)
    for _ in range(25):
        try:
            msg = recv_frame(s)
            if not msg: continue
            if msg.get('id') == 12:
                print('TASK 4 KPIS RESULT:')
                print(json.dumps(msg.get('result', {}).get('result', {}).get('value', {}), indent=2, ensure_ascii=False))
                break
        except socket.timeout:
            break
finally:
    proc.terminate()
