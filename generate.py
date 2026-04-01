#!/usr/bin/env python3
"""
Gemini Image Generator - VERIFIED WORKING
Model: gemini-2.0-flash-preview-image-generation
Source: developers.googleblog.com (official)
"""

from google import genai
from google.genai import types
import base64, os, time, json
from pathlib import Path

# ── API Key ──────────────────────────────────────────────
KEY_ID  = int(os.environ.get("KEY_ID", "1"))
API_KEY = os.environ.get(f"GEMINI_KEY_{KEY_ID}", "")

if not API_KEY:
    print(f"ERROR: Secret GEMINI_KEY_{KEY_ID} not found in GitHub Secrets!")
    exit(1)

# ── Load prompts.txt ─────────────────────────────────────
src = Path("prompts.txt")
if not src.exists():
    print("ERROR: prompts.txt not found in repo root!")
    exit(1)

ALL = [
    line.strip()
    for line in src.read_text("utf-8").splitlines()
    if line.strip() and not line.strip().startswith("#")
]
TOTAL = len(ALL)

# Key 1 handles: index 0,2,4... (images 1,3,5...)
# Key 2 handles: index 1,3,5... (images 2,4,6...)
mine = [(i, ALL[i]) for i in range(TOTAL) if i % 2 == (KEY_ID - 1)]

print(f"{'='*50}")
print(f"Key {KEY_ID} | {len(mine)} prompts | Total: {TOTAL}")
print(f"Model: gemini-2.0-flash-preview-image-generation")
print(f"{'='*50}")

# ── Setup client ─────────────────────────────────────────
client = genai.Client(api_key=API_KEY)

OUT = Path("output")
OUT.mkdir(exist_ok=True)

# ── Generate one image ───────────────────────────────────
def make_image(prompt: str) -> bytes | None:
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash-preview-image-generation",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]
                )
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    data = part.inline_data.data
                    # data is already bytes here
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    if len(data) > 5000:
                        return data
            print(f"  attempt {attempt}: no image in response")

        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "exhausted" in err.lower():
                print(f"  rate limit hit — sleeping 65s...")
                time.sleep(65)
            elif "400" in err or "blocked" in err.lower():
                print(f"  blocked/bad request — skipping")
                return None
            else:
                print(f"  error attempt {attempt}/3: {err[:70]}")
                if attempt < 3:
                    time.sleep(attempt * 5)
    return None

# ── Main loop ────────────────────────────────────────────
ok = fail = 0

for idx, prompt in mine:
    n    = idx + 1
    path = OUT / f"{n}.png"

    if path.exists() and path.stat().st_size > 5000:
        print(f"skip  {n}.png (exists)")
        ok += 1
        continue

    print(f"\ngen   {n}/{TOTAL}: {prompt[:60]}...")
    data = make_image(prompt)

    if data:
        path.write_bytes(data)
        print(f"saved {n}.png ({len(data)//1024} KB)")
        ok += 1
    else:
        print(f"FAIL  {n}.png")
        fail += 1

    # Rate limit: 10 RPM max → wait 7s between calls
    if idx < mine[-1][0]:
        time.sleep(7)

# ── Summary ──────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"Key {KEY_ID} done: {ok} saved, {fail} failed")
print(f"{'='*50}")

(OUT / f"report_{KEY_ID}.json").write_text(
    json.dumps({"key": KEY_ID, "ok": ok, "fail": fail})
)
