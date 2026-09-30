import time,json,urllib.request,urllib.error,base64,uuid,os,sys
from threading import Thread
from flask import Flask
import nacl.signing,base58

app=Flask(__name__)
@app.route('/')
def home():
    return "Flop Agent is running!"
def run_server():
    app.run(host='0.0.0.0',port=8080)

key_hex=os.environ.get("AGENT_KEY_HEX")
if not key_hex:
    print("ERROR: Set AGENT_KEY_HEX in Secrets!");sys.exit(1)
key=nacl.signing.SigningKey(bytes.fromhex(key_hex))
pub_bytes=b'\xed\x01'+key.verify_key.encode()
did_key="did:key:z"+base58.b58encode(pub_bytes).decode()
nc=2
RM="close1"

def post(obj):
    global nc
    t=json.dumps(obj,separators=(',',':'),sort_keys=True)
    s=key.sign(f"{RM}|{nc}|{t}".encode()).signature
    s64=base64.urlsafe_b64encode(s).decode().rstrip("=")
    p={"did":did_key,"sig":s64,"nonce":str(nc),"text":t}
    d=json.dumps(p).encode()
    r=urllib.request.Request(f"https://technocore.chat/r/{RM}",data=d,headers={"Content-Type":"application/json"})
    try:
        urllib.request.urlopen(r);print(f"[{nc}] OK",flush=True);nc+=1
    except urllib.error.HTTPError as e:
        print(f"[{nc}] Fail:{e.read().decode()}",flush=True);nc+=1

def get_price():
    try:
        r=urllib.request.urlopen("https://technocore.chat/r/d-close1-price?limit=10")
        for l in reversed(r.read().decode().strip().split('\n')):
            if '"t":"price"' in l:
                d=json.loads(l.split(' ',3)[-1]);return float(d["ref"]["px"]),d["n"]
    except Exception as e:
        print("Err:",e,flush=True)
    return None,None

def offer(px,side,sn):
    tm={"id":"t_"+uuid.uuid4().hex[:8],"maker":did_key,"px":f"{px:.2f}","qty":"5.00","side":side,"taker":"any","until":sn+5}
    tt=json.dumps(tm,separators=(',',':'),sort_keys=True)
    ms=base64.urlsafe_b64encode(key.sign(f"close-1|terms|{tt}".encode()).signature).decode().rstrip("=")
    print(f"{side.upper()} @ {px:.2f}",flush=True)
    post({"t":"trade","season":"close-1","terms":tm,"taker":"any","maker_sig":ms})

if __name__=="__main__":
    Thread(target=run_server).start()
    print(f"Bot: {did_key}",flush=True)
    pr,ls=[],0
    while True:
        px,sn=get_price()
        if px and sn and sn>ls:
            pr.append(px)
            if len(pr)>6:pr.pop(0)
            ma=sum(pr)/len(pr);ls=sn
            print(f"S{sn} P{px} MA{ma:.2f}",flush=True)
            if len(pr)>=2:
                if px>ma+0.15:offer(px+0.05,"sell",sn)
                elif px<ma-0.15:offer(px-0.05,"buy",sn)
                else:offer(px-0.15,"buy",sn);offer(px+0.15,"sell",sn)
        time.sleep(60)
