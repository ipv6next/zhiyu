import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import server
import interviews as iv
import lightweight_twin as light


class InterviewTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.old=server.DB
        server.DB=Path(self.folder.name)/'isolated.sqlite3';self.db=server.connect()
        self.env=patch.dict(os.environ,{'DEEPSEEK_API_KEY':'fake-test-key'});self.env.start()

    def tearDown(self):
        self.db.close();server.DB=self.old;self.env.stop();self.folder.cleanup()

    def engine(self,context):
        return {'ack':'听到了，你很在意相处的感受。','suggest_followup':True,'followup':'这种时候，什么样的小举动让你舒服？','next_question':'你希望共同时间和个人空间怎样平衡？','evidence':[]},{'prompt_tokens':100,'completion_tokens':60,'total_tokens':160}

    def start(self,actor='demo_member',**kwargs):
        return iv.start(self.db,actor,kwargs,engine=self.engine)

    def act(self,result,operation,actor='demo_member',engine=None,**kwargs):
        s=result['state']
        return iv.act(self.db,actor,{'id':s['id'],'revision':s['revision'],'operation':operation,**kwargs},engine=engine or self.engine)

    def test_additive_schema_does_not_change_old_answers_or_settings(self):
        server.save_relationship_questionnaire(self.db,'demo_member',{'conflict_timing':'cool_then_talk'})
        before=server.twin_profile(self.db,'demo_member');self.start();iv.setup(self.db)
        self.assertEqual(before,server.twin_profile(self.db,'demo_member'))
        self.assertEqual(server.relationship_questionnaire(self.db,'demo_member')['answered_count'],1)

    def test_pause_resume_persistent_draft_and_no_idle_clock(self):
        result=self.start();result=self.act(result,'pause',text='稍后再说的草稿')
        self.db.commit();self.db.close();self.db=server.connect()
        with patch.object(iv.time,'time',return_value=iv.time.time()+86400):result=self.act(result,'resume')
        self.assertEqual(result['state']['draft'],'稍后再说的草稿')
        self.assertLess(result['state']['active_seconds'],10)
        self.assertEqual(len(result['messages']),1)

    def test_one_followup_and_skipped_topics_never_return(self):
        result=self.start();result=self.act(result,'message',text='我喜欢散步')
        self.assertEqual(result['state']['followups'],1)
        result=self.act(result,'message',text='我希望一起散步')
        self.assertEqual(result['state']['topic'],1)
        result=self.act(result,'skip');self.assertEqual(result['state']['topic'],2)
        result=self.act(result,'message',text='不想回答这个')
        self.assertEqual(result['state']['topic'],3)
        result=self.act(result,'skip');self.assertEqual(result['state']['status'],'completed')
        self.assertEqual(result['state']['done'],[0,1,2,3])

    def test_change_followup_does_not_reset_allowance(self):
        result=self.act(self.start(),'message',text='我喜欢看电影')
        result=self.act(result,'change')
        self.assertEqual(result['state']['topic'],1)
        self.assertIn(0,result['state']['done'])

    def test_manual_ending_and_time_limit(self):
        result=self.act(self.start(),'finish',text='未发送草稿')
        self.assertEqual(result['state']['status'],'completed')
        self.assertEqual(result['state']['draft'],'未发送草稿')
        result=self.start();s=result['state'];s['active_seconds']=301;iv.persist(self.db,'demo_member',s)
        result=iv.view(self.db,'demo_member',s['id'])
        result=self.act(result,'message',text='我喜欢做饭')
        self.assertEqual(result['state']['status'],'completed')

    def test_model_failure_commits_answer_and_does_not_lose_progress(self):
        def broken(_):raise TimeoutError('provider timeout')
        result=self.start();result=self.act(result,'message',text='我希望先冷静一下再沟通',engine=broken)
        with closing(sqlite3.connect(server.DB)) as another:
            saved=another.execute('SELECT content FROM interview_messages WHERE user_id=? AND session_id=?',('demo_member',result['state']['id'])).fetchall()
            self.assertTrue(any(m[0]=='我希望先冷静一下再沟通' for m in saved))
        self.assertIn('已保存',result['state']['notice'])
        self.assertEqual(self.db.execute("SELECT status FROM interview_model_calls ORDER BY rowid DESC LIMIT 1").fetchone()[0],'failed')

    def test_revision_conflict_and_bounds_do_not_append(self):
        result=self.start();self.act(result,'message',text='我喜欢散步')
        with self.assertRaises(ValueError):self.act(result,'message',text='旧标签页')
        result=iv.view(self.db,'demo_member',result['state']['id']);before=len(result['messages'])
        with self.assertRaises(ValueError):self.act(result,'message',text='字'*801)
        self.assertEqual(len(iv.messages(self.db,'demo_member',result['state']['id'])),before)

    def test_model_limits_and_account_daily_budget(self):
        result=self.start();s=result['state'];s['calls']=iv.MAX_CALLS;iv.persist(self.db,'demo_member',s)
        result=iv.view(self.db,'demo_member',s['id'])
        def must_not_call(_):raise AssertionError('budget bypass')
        result=self.act(result,'message',text='我喜欢散步',engine=must_not_call)
        self.assertEqual(result['state']['calls'],iv.MAX_CALLS)
        for i in range(iv.DAILY_CALLS):
            self.db.execute('INSERT INTO interview_model_calls VALUES (?,?,?,?,?,?)',(str(i),'demo_member',s['id'],iv.time.time(),'failed','{}'))
        result=self.act(result,'finish');result=iv.start(self.db,'demo_member',{},engine=must_not_call)
        self.assertEqual(result['state']['calls'],0)

    def test_known_eleven_answers_inform_question_not_rewrite(self):
        server.save_relationship_questionnaire(self.db,'demo_member',{'conflict_timing':'cool_then_talk'})
        context=[]
        def capture(c):context.append(c);return {},{}
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':''}): result=iv.start(self.db,'demo_member',{'topic':'communication'},engine=capture)
        self.assertIn('先缓一缓',result['messages'][0]['content'])
        self.assertEqual(server.relationship_questionnaire(self.db,'demo_member')['answered_count'],1)

    def test_evidence_quote_preserves_negation_and_rejects_inference_sensitive(self):
        answer='我不喜欢频繁联系，工作日希望安静一点'
        self.assertTrue(iv.direct_ordinary_quote(answer,answer))
        for quote,raw in [('我喜欢频繁联系',answer),('我喜欢徒步','朋友说：我喜欢徒步'),('我喜欢徒步','这是朋友说的话。\n我喜欢徒步'),('我希望结婚后辞职，多点时间相处','我希望结婚后辞职，多点时间相处'),('我喜欢跑步，住在某某路123号','我喜欢跑步，住在某某路123号')]:
            self.assertFalse(iv.direct_ordinary_quote(quote,raw))
        result=self.start(scope='ordinary')
        def infer(_):return {'evidence':[{'quote':'我是回避型人格'},{'quote':'我喜欢频繁联系'}]},{}
        result=self.act(result,'message',text=answer,engine=infer)
        self.assertEqual([e['quote'] for e in result['evidence']],[answer])

    def test_permission_revocation_and_deletion_affect_existing_room(self):
        result=self.start(scope='private');result=self.act(result,'message',text='我喜欢散步')
        light.save_consent(self.db,'demo_member',True)
        room=server.request_premeet_room(self.db,'demo_candidate','demo_member')
        self.assertNotIn('我喜欢散步',server.conversation_prompt(room))
        result=self.act(result,'scope',scope='ordinary');server.refresh_room_twin(self.db,room)
        self.assertIn('我喜欢散步',server.conversation_prompt(room))
        room['messages']=[{'role':'user','content':'旧普通偏好'},{'role':'assistant','content':'我喜欢散步'}]
        result=self.act(result,'scope',scope='private');server.refresh_room_twin(self.db,room)
        self.assertEqual(room['_expression_history_start'],2)
        self.assertNotIn('我喜欢散步',server.conversation_prompt(room))
        result=self.act(result,'scope',scope='ordinary')
        result=self.act(result,'delete_evidence',evidence_id=result['evidence'][0]['id'])
        self.assertEqual(iv.expression_evidence(self.db,'demo_member'),[])

    def test_edit_replaces_evidence_without_altering_original_message(self):
        result=self.act(self.start(scope='ordinary'),'message',text='我喜欢散步')
        result=self.act(result,'edit_evidence',evidence_id=result['evidence'][0]['id'],text='我喜欢看电影')
        self.assertEqual([e['quote'] for e in result['evidence']],['我喜欢看电影'])
        self.assertTrue(any(m['content']=='我喜欢散步' for m in result['messages']))

    def test_account_session_memory_and_context_are_isolated(self):
        other=server.create_local_account(self.db,'虚构另一个主人')['user']['id'];server.set_membership_entitlement(self.db,other,'active')
        a=self.act(self.start(),'message',text='我喜欢散步，尤其是早晨')
        b=self.start(actor=other)
        def check(context):
            self.assertNotIn('尤其是早晨',json.dumps(context,ensure_ascii=False))
            return self.engine(context)
        b=self.act(b,'message',actor=other,text='我喜欢看电影',engine=check)
        self.assertNotIn('看电影',json.dumps(iv.view(self.db,'demo_member',a['state']['id'])['messages'],ensure_ascii=False))
        with self.assertRaises(ValueError):iv.view(self.db,other,a['state']['id'])
        with self.assertRaises(ValueError):self.act(a,'skip',actor=other)
        with self.assertRaises(ValueError):self.act(b,'delete_evidence',actor=other,evidence_id=a['evidence'][0]['id'])
        self.assertNotEqual(iv.start(self.db,other,{})['state']['id'],a['state']['id'])

    def test_provider_schema_and_token_usage(self):
        def capture(payload,**kwargs):
            self.assertEqual(payload['thinking'],{'type':'disabled'});self.assertEqual(payload['max_tokens'],600)
            return {'choices':[{'message':{'content':'not json'}}],'usage':{'total_tokens':17}}
        with patch.object(iv,'chat',side_effect=capture):
            with self.assertRaises(ValueError) as ctx:iv.provider({'current_answer':'我喜欢散步'})
            result=iv.start(self.db,'demo_member',{},engine=iv.provider)
        self.assertEqual(ctx.exception.usage,{'total_tokens':17})
        row=self.db.execute('SELECT status,usage FROM interview_model_calls ORDER BY rowid DESC LIMIT 1').fetchone()
        self.assertEqual(row['status'],'failed');self.assertEqual(json.loads(row['usage']),{'total_tokens':17})

    def test_opening_cannot_ask_next_topic(self):
        def wrong(context):
            self.assertIsNone(context['next'])
            self.assertIsNone(context['question_plan']['next'])
            return {'next_question':iv.TOPICS[1]['question']},{}
        result=iv.start(self.db,'demo_member',{},engine=wrong)
        self.assertEqual(result['state']['topic'],0)
        self.assertEqual(iv.question_text(result['messages'][-1]['content']),iv.TOPICS[0]['question'])
        self.assertEqual(result['messages'][-1]['source'],'preset')

    def test_cross_topic_followup_is_rejected(self):
        result=self.start(topic='communication')
        def wrong(context):
            self.assertEqual(context['question_plan']['followup']['topic'],'communication')
            return {'ack':'听起来你很在意平静沟通。','suggest_followup':True,'followup':'忙完一天，有什么习惯能让你心平气和？'},{}
        result=self.act(result,'message',text='情绪稳定，心平气和的沟通',engine=wrong)
        question=iv.question_text(result['messages'][-1]['content'])
        self.assertNotIn('忙完一天',question)
        self.assertIn('回应',question)
        self.assertEqual(result['state']['topic'],1)

    def test_next_topic_cannot_repeat_previous_topic_question(self):
        result=self.start()
        def wrong(_):return {'suggest_followup':False,'next_question':'忙完一天之后，你一般怎样让自己放松下来？'},{}
        result=self.act(result,'message',text='看书，或者听音乐',engine=wrong)
        self.assertEqual(result['state']['topic'],1)
        self.assertIn('意见不一致',result['messages'][-1]['content'])
        self.assertEqual(len({iv.normalized_question(q['text']) for q in result['state']['asked_questions']}),2)

    def test_repeated_change_returns_distinct_intents_then_changes_topic(self):
        result=self.start();seen=[iv.question_text(result['messages'][-1]['content'])]
        def repeats(_):return {'next_question':iv.TOPICS[0]['question']},{}
        for _ in range(3):
            result=self.act(result,'change',engine=repeats)
            seen.append(iv.question_text(result['messages'][-1]['content']))
        self.assertEqual(len(set(seen)),4)
        self.assertEqual(result['state']['topic'],1)
        self.assertEqual([q['intent'] for q in result['state']['asked_questions']][:3],['relax','weekend','discover'])

    def test_duplicate_feedback_does_not_call_model_or_ask_again(self):
        result=self.start();calls=result['state']['calls']
        def forbidden(_):raise AssertionError('duplicate feedback must skip the model')
        result=self.act(result,'message',text='这个问题前面回答过了',engine=forbidden)
        self.assertEqual(result['state']['calls'],calls)
        self.assertEqual(result['state']['topic'],1)
        self.assertIn('不再重复',result['messages'][-1]['content'])

    def test_asked_memory_survives_resume_and_legacy_backfill(self):
        result=self.act(self.start(),'change')
        result=self.act(result,'pause');self.db.commit()
        result=self.act(result,'resume')
        self.assertEqual(len(result['state']['asked_questions']),2)
        # Simulate a pre-fix session: its original messages remain byte-for-byte.
        state=result['state'];state.pop('asked_questions');state.pop('message_sources',None)
        self.db.execute('UPDATE interview_sessions SET data=? WHERE id=?',(json.dumps(state),state['id']))
        restored=iv.view(self.db,'demo_member',state['id'])
        self.assertEqual([m['content'] for m in restored['messages']],[m['content'] for m in result['messages']])
        self.assertEqual(len(restored['state']['asked_questions']),2)
        next_result=self.act(restored,'change')
        self.assertEqual(next_result['state']['asked_questions'][-1]['intent'],'discover')

    def test_generation_sources_reflect_model_and_presets(self):
        def good(_):return {'next_question':'忙完一天，你会做什么来放松？'},{}
        result=iv.start(self.db,'demo_member',{},engine=good)
        self.assertEqual(result['messages'][-1]['source'],'ai_generated')
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':''}):result=self.act(result,'change')
        self.assertEqual(result['messages'][-1]['source'],'preset')
        self.assertEqual(result['state']['generation_reason'],'no_key')

    def test_delete_account_cleans_interview_data(self):
        self.act(self.start(),'message',text='我喜欢散步')
        server.account_apply(self.db,{'actor':'demo_member','action':'delete_account'})
        for table in ('interview_sessions','interview_messages','interview_evidence','interview_model_calls'):
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM '+table+' WHERE user_id=?',('demo_member',)).fetchone()[0],0)

    def test_global_consent_also_gates_interview_preferences(self):
        self.act(self.start(scope='ordinary'),'message',text='我喜欢看电影')
        light.save_consent(self.db,'demo_member',True)
        room=server.request_premeet_room(self.db,'demo_candidate','demo_member')
        self.assertIn('我喜欢看电影',server.conversation_prompt(room))
        light.save_consent(self.db,'demo_member',False);server.refresh_room_twin(self.db,room)
        self.assertNotIn('我喜欢看电影',server.conversation_prompt(room))

    def test_http_identity_overrides_forged_actor_and_foreign_session_id(self):
        owner=server.create_local_account(self.db,'虚构甲');other=server.create_local_account(self.db,'虚构乙')
        for account in (owner,other):server.set_membership_entitlement(self.db,account['user']['id'],'active')
        self.db.commit();http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def post(account,**data):
            req=Request('http://127.0.0.1:'+str(http.server_port)+'/api/account',data=json.dumps({'session':account['session'],**data}).encode(),headers={'Content-Type':'application/json'})
            with urlopen(req) as response:return json.load(response)
        try:
            with patch.dict(os.environ,{'DEEPSEEK_API_KEY':''}):
                a=post(owner,action='interview_start',actor=other['user']['id'])
                b=post(other,action='interview_start')
                self.assertNotEqual(a['state']['id'],b['state']['id'])
                with self.assertRaises(HTTPError):post(other,action='interview_me',id=a['state']['id'])
            captures=[]
            def provider(payload,**kwargs):
                context=json.loads(payload['messages'][1]['content']);captures.append(context)
                output={'ack':'谢谢你分享。','suggest_followup':True,'followup':'你更喜欢独处还是一起放松？','evidence':[]}
                return {'choices':[{'message':{'content':json.dumps(output,ensure_ascii=False)}}],'usage':{'total_tokens':12}}
            with patch.object(iv,'chat',side_effect=provider),ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(post,account,action='interview_act',id=snapshot['state']['id'],revision=snapshot['state']['revision'],operation='message',text=text) for account,snapshot,text in ((owner,a,'我喜欢散步，享受早晨'),(other,b,'我喜欢看电影，享受放松'))]
                results=[f.result() for f in futures]
            self.assertEqual(len(captures),2)
            for context in captures:
                raw=json.dumps(context,ensure_ascii=False)
                self.assertFalse('享受早晨' in raw and '享受放松' in raw)
            self.assertNotIn('享受放松',json.dumps(results[0]['messages'],ensure_ascii=False))
            self.assertNotIn('享受早晨',json.dumps(results[1]['messages'],ensure_ascii=False))
        finally:http.shutdown();http.server_close();thread.join()


if __name__=='__main__':unittest.main()
