import asyncio, json, os, sys
import websockets

MODELS = [
    # Diffusion models
    {"id": 2060527, "type": "Stable-Diffusion", "name": "wan22I2VA14BGGUF_q8A14BHigh.gguf"},
    {"id": 2060943, "type": "Stable-Diffusion", "name": "wan22I2VA14BGGUF_q8A14BLow.gguf"},
    {"id": 2584698, "type": "Stable-Diffusion", "name": "wan22EnhancedNSFWCameraPrompt_nsfwV2Q8High.gguf"},
    {"id": 2584707, "type": "Stable-Diffusion", "name": "wan22EnhancedNSFWCameraPrompt_nsfwV2Q8Low.gguf"},
    {"id": 2367702, "type": "Stable-Diffusion", "name": "wan22EnhancedNSFWCameraPrompt_v2CAMI2VFP8HIGH.safetensors"},
    {"id": 2367780, "type": "Stable-Diffusion", "name": "wan22EnhancedNSFWCameraPrompt_v2CAMI2VFP8LOW.safetensors"},
    {"id": 290640, "type": "Stable-Diffusion", "name": "ponyDiffusionV6XL_v6StartWithThisOne.safetensors"},
    {"id": 923681, "type": "Stable-Diffusion", "name": "uberRealisticPornMergePonyxl_ponyxlHybridV1.safetensors"},
    {"id": 501240, "type": "Stable-Diffusion", "name": "realisticVisionV60B1_v51HyperVAE.safetensors"},
    {"id": 915814, "type": "Stable-Diffusion", "name": "uberRealisticPornMerge_v23Final.safetensors"},
    # LoRAs
    {"id": 2090326, "type": "LoRA", "name": "Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors"},
    {"id": 2090344, "type": "LoRA", "name": "Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors"},
    {"id": 2079658, "type": "LoRA", "name": "WAN2.2-HighNoise_SmartphoneSnapshotPhotoReality_v3_by-AI_Characters.safetensors"},
    {"id": 2079614, "type": "LoRA", "name": "WAN2.2-LowNoise_SmartphoneSnapshotPhotoReality_v3_by-AI_Characters.safetensors"},
    {"id": 1776890, "type": "LoRA", "name": "big_breasts_v2_epoch_30.safetensors"},
    {"id": 984672, "type": "LoRA", "name": "aidmaImageUprader-FLUX-v0.3.safetensors"},
    {"id": 1301668, "type": "LoRA", "name": "aidmaRealisticSkin-FLUX-v0.1.safetensors"},
    {"id": 2546506, "type": "LoRA", "name": "Flux.2 D - 2000s style.safetensors"},
    {"id": 263005, "type": "LoRA", "name": "igbaddie.safetensors"},
    {"id": 87153, "type": "LoRA", "name": "more_details.safetensors"},
    {"id": 556208, "type": "LoRA", "name": "igbaddie-PN.safetensors"},
    {"id": 2074888, "type": "LoRA", "name": "Realism Lora By Stable Yogi_V3_Lite.safetensors"},
    {"id": 1071060, "type": "LoRA", "name": "Super_Eye_Detailer_By_Stable_Yogi_SDPD0.safetensors"},
    # Embeddings
    {"id": 775151, "type": "Embedding", "name": "Stable_Yogis_PDXL_Positives.safetensors"},
    {"id": 772342, "type": "Embedding", "name": "Stable_Yogis_PDXL_Negatives-neg.safetensors"},
    {"id": 145996, "type": "Embedding", "name": "epiCPhotoGasm-colorfulPhoto-neg.pt"},
]

async def download(m, token, session_id, sem):
    async with sem:
        print(f"[{m['id']}] Starting {m['name']}...", flush=True)
        try:
            async with websockets.connect("ws://localhost:17865/API/DoModelDownloadWS", close_timeout=1800) as ws:
                payload = {
                    "session_id": session_id,
                    "url": f"https://civitai.com/api/download/models/{m['id']}?token={token}",
                    "type": m["type"],
                    "name": m["name"]
                }
                await ws.send(json.dumps(payload))
                last_pct = 0
                async for msg in ws:
                    d = json.loads(msg)
                    if "progress" in d:
                        pct = int(d["progress"] * 100)
                        if pct >= last_pct + 20:
                            print(f"[{m['id']}] {pct}%", flush=True)
                            last_pct = pct
                    elif "success" in d:
                        print(f"[{m['id']}] SUCCESS", flush=True)
                        return True
                    elif "error" in d:
                        err = d.get("error", "unknown")
                        print(f"[{m['id']}] ERROR: {err}", flush=True)
                        return False
        except Exception as e:
            print(f"[{m['id']}] Exception: {e}", flush=True)
            return False

async def main():
    token = os.environ.get("CIVITAI_TOKEN")
    session_id = os.environ.get("SESSION_ID")
    print(f"Downloading {len(MODELS)} models...", flush=True)
    sem = asyncio.Semaphore(2)
    results = await asyncio.gather(*[download(m, token, session_id, sem) for m in MODELS])
    success = sum(1 for r in results if r is True)
    print(f"Complete: {success}/{len(MODELS)}", flush=True)

asyncio.run(main())
