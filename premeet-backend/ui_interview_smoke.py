"""Optional browser test: isolated DB, three fictional accounts, scripted provider.
Run with the dev-only .tools/light-ui-test Python while port 4180 is free.
"""
import json
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
import server
import interviews as iv


def fake_provider(payload,**kwargs):
    context=json.loads(payload['messages'][1]['content'])
    topic=context['current'];next_topic=context['next']
    output={'ack':'听到了，你很在意相处时的感受。','suggest_followup':bool(context['may_follow_up']),
            'followup':context['question_plan']['followup']['question'] if context['question_plan']['followup'] else '',
            'next_question':topic['question'] if context['opening'] else next_topic['question'] if next_topic else '',
            'evidence':[]}
    return {'choices':[{'message':{'content':json.dumps(output,ensure_ascii=False)}}],'usage':{'prompt_tokens':90,'completion_tokens':45,'total_tokens':135}}


def premeet_provider(payload,**kwargs):
    raw=json.dumps(payload,ensure_ascii=False)
    text='我喜欢散步，也享受安静放松。你平时怎样放松？' if '我喜欢散步' in raw else '这个偏好我还不确定（本人未提及）。你愿意说说你的想法吗？'
    return {'choices':[{'message':{'content':text}}]}


def run():
    original=server.DB
    with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'DEEPSEEK_API_KEY':'fake-test-key'}),patch.object(iv,'chat',side_effect=fake_provider),patch.object(server,'model_chat',side_effect=premeet_provider):
        server.DB=Path(folder)/'ui-interview.sqlite3';db=server.connect()
        accounts=[server.create_local_account(db,name) for name in ('虚构访谈小禾','虚构访谈阿宁','虚构来访小林')]
        for i,account in enumerate(accounts):
            uid=account['user']['id']
            if i<2:server.set_membership_entitlement(db,uid,'active')
            before=server.own_profile(db,uid)
            server.save_public_profile(db,uid,{'nickname':account['user']['nickname'],'city':'杭州'},before['version'])
            prefs=server.match_preferences(db,uid);prefs['accept_distance']=True
            db.execute('UPDATE match_preferences SET data=? WHERE user_id=?',(json.dumps(prefs),uid))
        db.commit();db.close()
        http=ThreadingHTTPServer(('127.0.0.1',4180),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
                pages=[];errors=[]
                for account in accounts:
                    context=browser.new_context(viewport={'width':390,'height':844})
                    context.add_init_script('localStorage.setItem("zhiyu-session",'+json.dumps(account['session'])+');localStorage.setItem("zhiyu-actor",'+json.dumps(account['user']['id'])+');')
                    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)));pages.append(page)
                a,b,visitor=pages
                for page in (a,b):
                    page.goto('http://127.0.0.1:4180/interview.html');page.locator('#start').wait_for(state='visible');page.locator('#initial-scope').check();page.locator('#start').click();page.locator('#composer').wait_for(state='visible')
                changed=[a.locator('#messages .assistant').last.inner_text()]
                for _ in range(2):
                    a.locator('#change').click();a.wait_for_function("!document.querySelector('#change').disabled")
                    changed.append(a.locator('#messages .assistant').last.inner_text())
                assert len(set(changed))==3
                assert 'DeepSeek 实时生成' in changed[-1]
                a.locator('#answer').fill('我喜欢散步');b.locator('#answer').fill('我喜欢看电影')
                a.locator('#send').click();b.locator('#send').click()
                for page in (a,b):page.locator('#messages .assistant').last.filter(has_text='享受这些兴趣').wait_for()
                assert '看电影' not in a.locator('#messages').inner_text()
                assert '散步' not in b.locator('#messages').inner_text()
                a.locator('#answer').fill('这段草稿稍后再说');a.locator('#pause').click();a.locator('#resume').wait_for(state='visible');a.reload();a.locator('#resume').click();a.locator('#composer').wait_for(state='visible')
                assert a.locator('#answer').input_value()=='这段草稿稍后再说'
                a.locator('#answer').fill('我希望先冷静一下再沟通');a.locator('#send').click();a.locator('#messages .assistant').last.filter(has_text='意见不一致').wait_for()
                assert '散步' in a.locator('#evidence').text_content()
                artifact=server.ROOT.parent/'.tools'/'interview-mobile.png';a.screenshot(path=str(artifact),full_page=True)
                assert a.evaluate('document.documentElement.scrollWidth<=innerWidth')
                def post(page,path,data):
                    return page.evaluate('''async ({path,data})=>{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const d=await r.json();if(!r.ok)throw Error(d.error);return d;}''',{'path':path,'data':data})
                post(a,'/api/account',{'action':'expression_consent','allowed':True})
                visitor.goto('http://127.0.0.1:4180/member.html')
                room=post(visitor,'/api/room',{'action':'request','member_id':accounts[0]['user']['id']})
                visitor.goto('http://127.0.0.1:4180/premeet.html?id='+room['id'])
                visitor.locator('#input').fill('周末喜欢怎么放松？');visitor.locator('#composer button').click();visitor.locator('#messages .message').last.filter(has_text='我喜欢散步').wait_for()
                a.locator('#scope').uncheck();a.locator('#save-scope').click()
                a.wait_for_function("document.querySelector('#save-scope').disabled===false")
                visitor.locator('#input').fill('还有什么兴趣？');visitor.locator('#composer button').click();visitor.locator('#messages .message').last.filter(has_text='本人未提及').wait_for()
                a.locator('#skip').click();a.locator('#progress').filter(has_text='个人空间').wait_for()
                a.locator('#finish').click();a.locator('#completed').wait_for(state='visible')
                a.locator('#evidence-panel summary').click();first=a.locator('.interview-evidence').first;first.get_by_role('button',name='修改',exact=True).click();first.locator('textarea').fill('我喜欢做饭');first.get_by_role('button',name='保存修改',exact=True).click()
                a.locator('#evidence').filter(has_text='我喜欢做饭').wait_for()
                a.locator('.interview-evidence').filter(has_text='我喜欢做饭').get_by_role('button',name='删除',exact=True).click()
                a.wait_for_function("!document.querySelector('#evidence').textContent.includes('我喜欢做饭')")
                a.set_viewport_size({'width':1366,'height':900});a.screenshot(path=str(artifact.with_name('interview-desktop.png')),full_page=True)
                a.goto('http://127.0.0.1:4180/member.html');a.locator('#interview-link').click();a.locator('#completed').wait_for(state='visible')
                assert not errors,errors
                browser.close();print('PASS: isolated owners, simultaneous conversations, draft pause/reload/resume, evidence edit/delete, premeeting consent/revocation, finish/resume entry, mobile/desktop; no page errors')
        finally:http.shutdown();http.server_close();thread.join();server.DB=original


if __name__=='__main__':run()
