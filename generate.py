#!/usr/bin/env python3
import google.genai as genai
import os, time, json
from pathlib import Path

KEY_ID  = int(os.environ.get("KEY_ID", "1"))
API_KEY = os.environ.get(f"GEMINI_KEY_{KEY_ID}", "")

if not API_KEY:
    print(f"ERROR: Secret GEMINI_KEY_{KEY_ID} not set!")
    exit(1)

src = Path("prompts.txt")
if not src.exists():
    print("ERROR: prompts.txt not found!")
    exit(1)

ALL = [l.strip() for l in src.read_text("utf-8").splitlines()
       if l.strip() and not l.startswith("#")]
TOTAL = len(ALL)
mine  = [(i, ALL[i]) for i in range(TOTAL) if i % 2 == (KEY_ID - 1)]

print(f"Key {KEY_ID} | {len(mine)} prompts | gemini-2.0-flash-exp")

client = genai.Client(api_key=API_KEY)
OUT = Path("output")
OUT.mkdir(exist_ok=True)

def make(prompt):
    for attempt in range(1, 4):
        try:
            resp = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_modalities=["IMAGE"]
                )
            )
            for part in resp.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    import base64
                    data = base64.b64decode(part.inline_data.data)
                    if len(data) > 5000:
                        return data
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                print(f"  rate limit — wait 65s")
                time.sleep(65)
            elif "400" in err:
                print(f"  bad request, skip")
                return None
            else:
                print(f"  error: {err[:60]}, retry {attempt}/3")
                time.sleep(attempt * 5)
    return None

ok = fail = 0
for idx, prompt in mine:
    n    = idx + 1
    path = OUT / f"{n}.png"

    if path.exists() and path.stat().st_size > 5000:
        print(f"skip {n}.png")
        ok += 1
        continue

    print(f"gen {n}/{TOTAL}: {prompt[:55]}...")
    data = make(prompt)

    if data:
        path.write_bytes(data)
        print(f"  saved {n}.png ({len(data)//1024}KB)")
        ok += 1
    else:
        print(f"  FAILED {n}.png")
        fail += 1

    time.sleep(7)

print(f"\nKey {KEY_ID}: {ok} ok, {fail} failed")
(OUT / f"report_{KEY_ID}.json").write_text(
    json.dumps({"key": KEY_ID, "ok": ok, "fail": fail})
)
