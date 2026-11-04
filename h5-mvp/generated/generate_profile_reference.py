import asyncio, base64, json, pathlib, re, sys
import websockets

ROOT = pathlib.Path(r"D:\AI\AI交友")
source = ROOT / "UI界面" / "UI-基本1.jpg"
out = ROOT / "h5-mvp" / "generated" / "profile-reference.html"

image_data = "data:image/jpeg;base64," + base64.b64encode(source.read_bytes()).decode("ascii")
payload = {
  "generationType": "create",
  "inputMode": "image",
  "prompt": {
    "text": "Create one responsive mobile H5 page for a new relationship-introduction product called 知遇. Use this screenshot only as an information hierarchy reference; create a clearly original visual design. Do not copy the source brand, its logo, exact wording, illustrations, or colors. The page is a profile onboarding form with sections: basic profile, relationship goals, preferences, and a consented AI digital-twin pre-meeting setting. Use a warm teal and peach palette, accessible Chinese typography, explicit privacy/consent microcopy, and a fixed primary action. Return a complete single HTML file with embedded CSS and no external assets.",
    "images": [image_data]
  },
  "history": [],
  "generatedCodeConfig": "html_css",
  "isImageGenerationEnabled": False,
  "isAssetExtractionEnabled": False,
  "openAiApiKey": None,
  "openAiBaseURL": None,
  "anthropicApiKey": None,
  "geminiApiKey": None,
  "replicateApiKey": None,
  "screenshotOneApiKey": None,
  "editorTheme": "cobalt",
  "selectedDesignSystemId": None,
  "isTermOfServiceAccepted": True
}

async def main():
    code = ""
    errors = []
    async with websockets.connect("ws://127.0.0.1:7001/generate-code", max_size=40 * 1024 * 1024, open_timeout=20, close_timeout=20) as ws:
        await ws.send(json.dumps(payload))
        async for raw in ws:
            msg = json.loads(raw)
            kind = msg.get("type")
            if kind == "setCode" and msg.get("variantIndex", 0) == 0:
                code = msg.get("value") or code
            elif kind == "variantError":
                errors.append(msg.get("value") or "generation error")
            elif kind == "error":
                errors.append(msg.get("value") or "generation error")
    if not code:
        raise RuntimeError("; ".join(errors)[:800] or "no generated code returned")
    code = re.sub(r"^```(?:html)?\s*", "", code.strip(), flags=re.I)
    code = re.sub(r"\s*```$", "", code)
    if "<html" not in code.lower():
        code = "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\"><title>知遇 · 资料档案</title></head><body>" + code + "</body></html>"
    out.write_text(code, encoding="utf-8")
    print(json.dumps({"Generated": True, "Output": str(out), "Characters": len(code), "Source": source.name}, ensure_ascii=False))

asyncio.run(main())
