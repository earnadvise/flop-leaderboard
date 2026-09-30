import time, json, urllib.request, urllib.error, base64, uuid, os, sys
from datetime import datetime, timedelta
import nacl.signing, base58

key_hex = os.environ.get("AGENT_KEY_HEX")
if not key_hex:
    print("ERROR: Set AGENT_KEY_HEX in GitHub Secrets!")
    sys.exit(1)

key = nacl.signing.SigningKey(bytes.fromhex(key_hex))
pub_bytes = b'\xed\x01' + key.verify_key.encode()
did_key = "did:key:z" + base58.b58encode(pub_bytes).decode()
nonce_counter = int(time.time())
ROOM = "close1"

def post_message(text_obj):
    global nonce_counter
    text = json.dumps(text_obj, separators=(',',':'), sort_keys=True)
    to_sign = f"{ROOM}|{nonce_counter}|{text}".encode('utf-8')
    sig = key.sign(to_sign).signature
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    payload = {"did": did_key, "sig": sig_b64, "nonce": str(nonce_counter), "text": text}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"https://technocore.chat/r/{ROOM}", data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req)
        print(f"[{nonce_counter}] Posted OK", flush=True)
        nonce_counter += 1
    except urllib.error.HTTPError as e:
        print(f"[{nonce_counter}] Fail: {e.read().decode()}", flush=True)
        nonce_counter += 1

def get_referee_price():
    try:
        req = urllib.request.Request("https://technocore.chat/r/d-close1-price?limit=10", headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req)
        lines = resp.read().decode().strip().split('\n')
        for line in reversed(lines):
            if '"t":"price"' in line:
                js_str = line.split(' ', 3)[-1]
                data = json.loads(js_str)
                return float(data["ref"]["px"]), data["n"]
    except Exception as e:
        print("Price err:", e, flush=True)
    return None, None

def make_offer(px, side, sweep_n, qty="40.00"):
    terms = {"id": "t_" + uuid.uuid4().hex[:8], "maker": did_key, "px": f"{px:.2f}", "qty": qty, "side": side, "taker": "any", "until": sweep_n + 5}
    terms_text = json.dumps(terms, separators=(',',':'), sort_keys=True)
    msig = base64.urlsafe_b64encode(key.sign(f"close-1|terms|{terms_text}".encode()).signature).decode().rstrip("=")
    msg = {"t": "trade", "season": "close-1", "terms": terms, "taker": "any", "maker_sig": msig}
    print(f"{side.upper()} qty {qty} @ {px:.2f}", flush=True)
    post_message(msg)

if __name__ == "__main__":
    print(f"GitHub Actions Bot started: {did_key}", flush=True)
    prices = []
    last_sweep = 0
    
    end_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    
    while datetime.utcnow() < end_time:
        px, sn = get_referee_price()
        if px and sn and sn > last_sweep:
            prices.append(px)
            if len(prices) > 6:
                prices.pop(0)
            ma = sum(prices) / len(prices)
            last_sweep = sn
            print(f"Sweep {sn} Price {px} MA {ma:.2f}", flush=True)
            
            # HIGH-LEVERAGE TOURNAMENT STRATEGY
            if len(prices) >= 2:
                if px > ma + 0.05:
                    make_offer(px + 0.01, "sell", sn, qty="40.00")
                elif px < ma - 0.05:
                    make_offer(px - 0.01, "buy", sn, qty="40.00")
                else:
                    # Neutral market - smaller spread size to prevent busting 10k limit if both hit
                    make_offer(px - 0.02, "buy", sn, qty="15.00")
                    make_offer(px + 0.02, "sell", sn, qty="15.00")
        time.sleep(60)
        
    print("Exiting gracefully after 5.5 hours for next cron cycle.")
