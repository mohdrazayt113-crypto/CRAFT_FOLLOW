import json
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import follow_pb2
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# ---------- Fixed encryption parameters ----------
KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# ---------- Region configuration ----------
REGION_CONFIG = {
    "ind": {
        "token_file": "token_ind.json",
        "base_url": "https://client.ind.freefiremobile.com"
    },
    "br": {
        "token_file": "token_br.json",
        "base_url": "https://client.us.freefiremobile.com"
    },
    "us": {
        "token_file": "token_br.json",
        "base_url": "https://client.us.freefiremobile.com"
    },
    "sac": {
        "token_file": "token_br.json",
        "base_url": "https://client.us.freefiremobile.com"
    },
    "na": {
        "token_file": "token_br.json",
        "base_url": "https://client.us.freefiremobile.com"
    }
}
# Default for any other region (e.g., "bd")
DEFAULT_CONFIG = {
    "token_file": "token_bd.json",
    "base_url": "https://clientbp.ggpolarbear.com"
}

def get_config(region):
    region = region.lower()
    return REGION_CONFIG.get(region, DEFAULT_CONFIG)

def encrypt_payload(data: bytes) -> bytes:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return cipher.encrypt(pad(data, AES.block_size))

def send_follow(target_id: int, jwt: str, base_url: str):
    """Send one follow request and return (success_bool, message)."""
    req = follow_pb2.CSFollowReq()
    req.target_id = target_id
    encrypted_data = encrypt_payload(req.SerializeToString())

    url = f"{base_url}/Follow"
    headers = {
        "User-Agent": "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Authorization": f"Bearer {jwt}",
        "X-Ga": "v1 1",
        "Releaseversion": "OB54",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2022.3.47f1",
    }

    try:
        resp = requests.post(url, headers=headers, data=encrypted_data, timeout=20)
    except Exception as e:
        return False, f"Network error: {e}"

    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}"

    # Optionally parse protobuf to confirm success flag
    try:
        res = follow_pb2.CSFollowRes()
        res.ParseFromString(resp.content)
        # If there's a success field, you can check it here.
        # For now, 200 OK means success.
        return True, "Success"
    except Exception as e:
        return False, f"Protobuf parse error: {e}"

def load_tokens(filename):
    """Load tokens from JSON file (array of objects with 'token' key)."""
    if not os.path.exists(filename):
        return []
    with open(filename, "r") as f:
        data = json.load(f)
    if isinstance(data, list):
        tokens = []
        for item in data:
            if "token" in item:
                tokens.append(item["token"])
        return tokens
    return []

def send_follows_bulk(target_id, tokens, base_url, desired_successes, max_workers=50):
    """
    Send follows in parallel using given tokens.
    Returns: (success_count, failed_count, results_list)
    """
    success_count = 0
    failed_count = 0
    results = []
    lock = threading.Lock()
    stop_event = threading.Event()

    # We'll submit all tokens, but we can stop early once desired successes achieved.
    # Use a ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # submit all tasks
        future_to_token = {executor.submit(send_follow, target_id, token, base_url): token for token in tokens}
        for future in as_completed(future_to_token):
            if stop_event.is_set():
                # skip processing remaining futures? We'll just ignore their results
                continue
            ok, msg = future.result()
            with lock:
                if ok:
                    success_count += 1
                    results.append({"status": "success", "message": msg})
                    if success_count >= desired_successes:
                        stop_event.set()
                else:
                    failed_count += 1
                    results.append({"status": "failed", "message": msg})
                # If we already have enough successes, we can break, but we still need to cancel other futures? 
                # We'll just break out of the loop when stop_event is set.
            if stop_event.is_set():
                # break from as_completed loop to stop processing further results
                # but we can't cancel already running, we'll just skip them.
                break

    return success_count, failed_count, results

@app.route('/follow', methods=['GET'])
def follow_endpoint():
    # Get parameters
    uid = request.args.get('uid')
    region = request.args.get('region', 'ind')
    targets_str = request.args.get('targets')
    threads_str = request.args.get('threads', '50')

    if not uid or not targets_str:
        return jsonify({"error": "Missing required parameters: uid and targets"}), 400

    try:
        target_id = int(uid)
        desired = int(targets_str)
        max_workers = int(threads_str)
        if desired <= 0 or max_workers <= 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "uid, targets, and threads must be positive integers"}), 400

    # Get region config
    config = get_config(region)
    token_file = config["token_file"]
    base_url = config["base_url"]

    # Load tokens
    tokens = load_tokens(token_file)
    if not tokens:
        return jsonify({"error": f"No tokens found in {token_file} for region {region}"}), 404

    # Limit workers to token count
    max_workers = min(max_workers, len(tokens))

    # Send follows
    success, failed, details = send_follows_bulk(target_id, tokens, base_url, desired, max_workers)

    response = {
        "region": region,
        "target_uid": target_id,
        "desired_successes": desired,
        "achieved_successes": success,
        "failed_attempts": failed,
        "tokens_used": success + failed,
        "details": details[:50]  # limit for response size; you can remove if you want all
    }
    return jsonify(response)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    # Run on 0.0.0.0 so it's accessible from outside (if needed)
    app.run(host='0.0.0.0', port=5000, debug=False)