from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import json
import urllib.parse
import os
import threading
import time
import logging
import traceback
import sys

NET_IFACE = os.getenv("NET_IFACE", "eth0")

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/srv/html/network_api.log")
    ]
)
logger = logging.getLogger("network_api")

# State persistent storage
STATE_FILE = "/srv/html/current_state.json"

def get_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"mode": "reset", "protocol": "h2"}

def save_state(mode):
    logger.info(f"Saving State: mode={mode}")
    with open(STATE_FILE, "w") as f:
        json.dump({"mode": mode}, f)

def run_command(cmd, ignore_errors=False):
    logger.debug(f"Executing command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if not ignore_errors:
            logger.error(f"Command failed with return code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
    else:
        if result.stdout: logger.debug(f"STDOUT: {result.stdout}")
        if result.stderr: logger.debug(f"STDERR: {result.stderr}")
    return result

PROFILES = {
    '2g': {"bw": "128kbit", "latency": "500ms", "loss": "5%"},
    '3g': {"bw": "2mbit", "latency": "100ms", "loss": "0.5%"},
    '4g': {"bw": "20mbit", "latency": "40ms", "loss": "0.2%"},
    'lte': {"bw": "50mbit", "latency": "20ms", "loss": "0%"},
    'wifi': {"bw": "100mbit", "latency": "15ms", "loss": "0.1%"},
    '5g': {"bw": "200mbit", "latency": "10ms", "loss": "0%"},
    'reset': {"bw": None, "latency": None, "loss": None}
}

def apply_tc_rules(mode):
    logger.info(f"Applying Network Profile: mode={mode}")
    run_command(["tc", "qdisc", "del", "dev", NET_IFACE, "root"], ignore_errors=True)
    run_command(["iptables", "-F", "OUTPUT"], ignore_errors=True)
    
    if mode in ['reset', 'wifi']:
        logger.info(f">>> Network {mode} (Actual/Unlimited)")
        save_state(mode)
        # Update label for UI
        label = "WIFI" if mode == "wifi" else "Unlimited"
        with open("/srv/html/network_profile.txt", "w") as f:
            f.write(label)
        return

    profile = PROFILES.get(mode, PROFILES['4g'])
    rate = profile['bw']
    delay = profile['latency']
    loss = profile['loss']

    run_command(["tc", "qdisc", "add", "dev", NET_IFACE, "root", "handle", "1:", "htb", "default", "1"])
    run_command(["tc", "class", "add", "dev", NET_IFACE, "parent", "1:", "classid", "1:1", "htb", "rate", rate, "ceil", rate])
    run_command(["tc", "qdisc", "add", "dev", NET_IFACE, "parent", "1:1", "handle", "10:", "netem", "delay", delay, "loss", loss])

    # Update labels for UI
    label = mode.upper() if mode != "reset" else "Unlimited"
    with open("/srv/html/network_profile.txt", "w") as f:
        f.write(label)
    
    save_state(mode)

class NetworkHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        logger.info(f"Incoming POST request: {self.path}")
        logger.debug(f"Headers: {dict(self.headers)}")
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        logger.debug(f"Raw Body: {post_data}")
        
        params = urllib.parse.parse_qs(post_data)
        logger.info(f"Parsed Parameters: {params}")
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        state = get_state()
        mode = params.get('mode', [state['mode']])[0]
        
        try:
            response = {"status": "success", "mode": mode, "received_params": params}
            self.wfile.write(json.dumps(response).encode())
            logger.info(f"Response Sent: {response}")
            
            def delayed_apply():
                time.sleep(1)
                try:
                    apply_tc_rules(mode)
                except Exception as ex:
                    logger.error(f"Error in delayed_apply: {ex}")
                    logger.error(traceback.format_exc())
                
            threading.Thread(target=delayed_apply).start()
        except Exception as e:
            logger.error(f"Error handling POST: {e}")
            logger.error(traceback.format_exc())
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())

    def do_OPTIONS(self):
        logger.info(f"Incoming OPTIONS request: {self.path}")
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    # Initial setup: No protocol enforcement on startup to avoid ERR_QUIC_PROTOCOL_ERROR
    # Just apply the default network profile (latency/bw)
    run_command(["tc", "qdisc", "del", "dev", NET_IFACE, "root"], ignore_errors=True)
    run_command(["iptables", "-F", "OUTPUT"], ignore_errors=True)
    
    state = get_state()
    apply_tc_rules(state['mode'])
    logger.info("Strict Network API listening on port 5000...")
    HTTPServer(('0.0.0.0', 5000), NetworkHandler).serve_forever()
