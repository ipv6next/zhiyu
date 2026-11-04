import asyncio, base64, json, pathlib, re
import websockets
ROOT = pathlib.Path(r"D:\AI\AI交友")
files = [ROOT / "UI界面" / x for x in ["UI-基本1.jpg", "UI-基础资料_3.jpg", "UI-交友偏好_4.jpg"]]
out = ROOT / "h5-mvp" / "generated" / "profile-wizard-reference.html"
def data_url(p):
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode("ascii")
payload = {
 "generationType":"create", "inputMode":"image",
 "prompt":{"text":"Design a complete original mobile-first H5 onboarding wizard for a Chinese relationship-introduction product called 知遇. Use the supplied screenshots solely to understand screen density, sections and interaction patterns. Do not copy any source brand, logo, mascot, wording, colors, layout assets, or screenshots. Create a distinct warm teal/ink/peach visual system. Include three tabs: 我的档案, 生活与婚恋, 匹配偏好. Cover verified core profile, city, education, work, album placeholders, relationship goals, personal tags, AI-red-match interview readiness, matching ranges and up to four must-have conditions. Include privacy visibility labels and an explicit digital-twin consent. Return a single responsive HTML document with embedded CSS and small vanilla JavaScript for selectable chips and tab switching. No external assets.","images":[data_url(p) for p in files]},
 "history":[],"generatedCodeConfig":"html_css","isImageGenerationEnabled":False,"isAssetExtractionEnabled":False,
 "openAiApiKey":None,"openAiBaseURL":None,"anthropicApiKey":None,"geminiApiKey":None,"replicateApiKey":None,"screenshotOneApiKey":None,"editorTheme":"cobalt","selectedDesignSystemId":None,"isTermOfServiceAccepted":True
}
async def main():
    code=''; errors=[]
    async with websockets.connect('ws://127.0.0.1:7001/generate-code', max_size=60*1024*1024, open_timeout=30, close_timeout=20) as ws:
        await ws.send(json.dumps(payload))
        async for raw in ws:
            m=json.loads(raw); kind=m.get('type')
            if kind=='setCode' and m.get('variantIndex',0)==0: code=m.get('value') or code
            elif kind in ('error','variantError'): errors.append(m.get('value') or 'generation error')
    if not code: raise RuntimeError('; '.join(errors)[:800] or 'No generated code returned')
    code=re.sub(r'^```(?:html)?\s*','',code.strip(),flags=re.I); code=re.sub(r'\s*```$','',code)
    out.write_text(code,encoding='utf-8')
    print(json.dumps({'Generated':True,'Output':str(out),'Characters':len(code),'InputImages':len(files)},ensure_ascii=False))
asyncio.run(main())
