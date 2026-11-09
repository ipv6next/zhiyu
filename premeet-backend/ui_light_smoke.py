"""Optional local browser smoke: run with a Python environment containing playwright.

Uses an isolated SQLite database and two fictional sessions, never real users.
Chrome is used from the local installation; no browser download is required.
"""
import json
import os
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from playwright.sync_api import sync_playwright
import server

def run():
    original=server.DB
    with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{'DEEPSEEK_API_KEY':''}):
        server.DB=Path(folder)/'ui.sqlite3'
        db=server.connect()
        owner=server.create_local_account(db,'虚构会员小禾');visitor=server.create_local_account(db,'虚构访客阿宁')
        oid=owner['user']['id'];vid=visitor['user']['id']
        server.set_membership_entitlement(db,oid,'active')
        for uid,name in ((oid,'虚构会员小禾'),(vid,'虚构访客阿宁')):
            current=server.own_profile(db,uid)
            server.save_public_profile(db,uid,{'nickname':name,'city':'杭州'},current['version'])
        db.commit();db.close()
        http=ThreadingHTTPServer(('127.0.0.1',4180),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
                contexts=[]
                for account in (owner,visitor):
                    context=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=1)
                    context.add_init_script('localStorage.setItem("zhiyu-session",'+json.dumps(account['session'])+');localStorage.setItem("zhiyu-actor",'+json.dumps(account['user']['id'])+');')
                    contexts.append(context)
                page=contexts[0].new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:4180/light-twin.html')
                page.locator('#choices button').first.wait_for();page.locator('#choices button').first.click();page.locator('#submit').click()
                page.locator('#question').filter(has_text='日常的小例子').wait_for()
                page.locator('#answer').fill('周末有时会在公园走一走')
                page.locator('#pause').click();page.locator('#resume').wait_for();page.reload();page.locator('#resume').click()
                assert page.locator('#answer').input_value()=='周末有时会在公园走一走'
                page.locator('#submit').click();page.locator('#question').filter(has_text='熟悉你的人').wait_for()
                page.locator('input[value="yes"]').check();page.locator('#save-consent').click()
                page.locator('#consent-note').filter(has_text='已保存').wait_for()
                artifact=server.ROOT.parent/'.tools'/'light-twin-mobile.png';page.screenshot(path=str(artifact),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                candidate=contexts[1].new_page();candidate.goto('http://127.0.0.1:4180/member.html')
                room=candidate.evaluate('''async id=>{let r=await fetch('/api/room',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'request',member_id:id})});let d=await r.json();if(!r.ok)throw Error(d.error);return d;}''',oid)
                candidate.goto('http://127.0.0.1:4180/premeet.html?id='+room['id']+'&actor='+vid)
                candidate.locator('h1').filter(has_text='虚构会员小禾').wait_for()
                candidate.locator('#input').fill('周末喜欢做什么？');candidate.locator('#composer button').click()
                candidate.locator('#messages .message').last.filter(has_text='运动或户外').wait_for()
                page.locator('input[value="no"]').check();page.locator('#save-consent').click()
                page.locator('#consent-note').filter(has_text='已保存').wait_for()
                candidate.locator('#input').fill('周末喜欢什么兴趣？');candidate.locator('#composer button').click()
                candidate.locator('#messages .message').last.filter(has_text='本人未提及').wait_for()
                candidate.on('dialog',lambda dialog:dialog.accept());candidate.locator('#end').click()
                candidate.wait_for_url('**/result.html?**')
                page.goto('http://127.0.0.1:4180/twin.html')
                page.locator('#light-entry').wait_for()
                assert not page.locator('#relationship-questions').is_visible()
                page.locator('summary').filter(has_text='原 11').click()
                page.locator('#relationship-questions').wait_for(state='visible')
                page.set_viewport_size({'width':1366,'height':900});page.goto('http://127.0.0.1:4180/light-twin.html')
                page.locator('#choices button').first.wait_for();page.screenshot(path=str(artifact.with_name('light-twin-desktop.png')),full_page=True)
                assert not errors,errors
                browser.close()
                print('PASS: two isolated sessions, answer/pause/reload/resume, consent/revoke, premeeting, result, legacy optional questions, mobile/desktop layouts; no page errors')
        finally:
            http.shutdown();http.server_close();thread.join();server.DB=original

if __name__=='__main__':run()
