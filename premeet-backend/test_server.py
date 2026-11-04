import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import server

class Rules(unittest.TestCase):
    def room(self):
        r=server.new_room();r['mode']='demo';return r
    def test_twenty_and_no_twentyfirst(self):
        r=self.room()
        for _ in range(20): server.apply(r,'message',{'text':'周末喜欢什么'})
        self.assertEqual((r['rounds'],len(r['messages']),r['status']),(20,40,'ended'))
        server.apply(r,'message',{'text':'再聊聊'})
        self.assertEqual(len(r['messages']),40)
    def test_deadline(self):
        r=self.room();r['deadline']=0
        server.apply(r,'message',{'text':'你好'})
        self.assertEqual(r['rounds'],0);self.assertEqual(r['status'],'ended')
    def test_response_arrives_late(self):
        r=self.room()
        def late(*args): r['deadline']=0;return 'late'
        with patch.object(server,'reply',late):server.apply(r,'message',{'text':'你好'})
        self.assertEqual(r['messages'],[])
    def test_both_consent(self):
        r=self.room()
        with self.assertRaises(ValueError):server.apply(r,'decision',{'role':'me','agree':True})
        server.apply(r,'end',{})
        server.apply(r,'decision',{'role':'me','agree':True})
        self.assertFalse(server.public(r)['unlocked'])
        server.apply(r,'decision',{'role':'owner','agree':True})
        self.assertTrue(server.public(r)['unlocked'])
        self.assertEqual(r['status'],'ready_for_handoff')
        server.apply(r,'decision',{'role':'owner','agree':False})
        self.assertFalse(server.public(r)['unlocked'])
    def test_failure_does_not_count(self):
        r=self.room()
        with patch.object(server,'reply',side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):server.apply(r,'message',{'text':'你好'})
        self.assertEqual(r['rounds'],0);self.assertEqual(r['messages'],[])
    def test_private_question(self):
        r=self.room();server.apply(r,'message',{'text':'你的微信是什么'})
        self.assertIn('（本人未提及）',r['messages'][-1]['content'])
        self.assertEqual(r['reply_sources'][0]['source'],'privacy_rule')
    def test_general_finance_is_not_blanket_blocked(self):
        r=self.room();server.apply(r,'message',{'text':'沟通时怎样讨论收入差距？'})
        self.assertNotIn('不能代答',r['messages'][-1]['content'])
        self.assertEqual(r['reply_sources'][0]['source'],'demo')
    def test_unknown_demo_answer_marks_not_mentioned(self):
        r=self.room();server.apply(r,'message',{'text':'你平时喜欢吃辣吗？'})
        self.assertIn('（本人未提及）',r['messages'][-1]['content'])
    def test_known_third_person_fallback_is_normalized(self):
        raw='甜食这块我没有可确认的偏好，不想替她编一个答案；你平时偏甜还是偏咸？（本人未提及）'
        answer=server.normalize_voice(raw)
        self.assertEqual(answer,'甜食这块我还没有特别明确的偏好；你平时偏甜还是偏咸？（本人未提及）')
    def test_analysis_is_cached_and_owner_notes_are_private(self):
        r=self.room();server.apply(r,'message',{'text':'你喜欢吃甜食吗？'});server.apply(r,'end',{})
        server.apply(r,'analysis',{})
        self.assertIn('【继续了解的可行性】',r['result_analysis'])
        self.assertEqual(r['analysis_mode'],'instant')
        self.assertEqual(r['owner_private_followups'],['你喜欢吃甜食吗？'])
        self.assertNotIn('owner_private_followups',server.public(r))
        first=r['result_analysis'];server.apply(r,'analysis',{});self.assertEqual(first,r['result_analysis'])
    def test_test_accounts_keep_private_data_out_of_public_profile(self):
        with server.connect() as db:
            users=server.account_apply(db,{'action':'list'})['users']
            # Local registration creates ordinary user accounts in addition to the
            # two stable regression identities.  The seeded identities must
            # remain available even when the local database has real test users.
            self.assertTrue({'demo_member','demo_candidate'}.issubset({user['id'] for user in users}))
            public=server.account_apply(db,{'action':'public_profile','actor':'demo_candidate','subject':'demo_member'})
            self.assertIn('city',public['profile'])
            self.assertNotIn('exact_address',public['profile'])
            self.assertNotIn('income_assets',public['profile'])
            own=server.account_apply(db,{'action':'me','actor':'demo_candidate'})
            saved=server.account_apply(db,{'action':'save_public','actor':'demo_candidate','version':own['version'],'public':{'nickname':'苏念','city':'南京','relationship_goal':'认真相处','interests':['城市漫步']}})
            self.assertEqual(saved['version'],own['version']+1)
            with self.assertRaises(ValueError):server.account_apply(db,{'action':'save_public','actor':'demo_candidate','version':saved['version'],'public':{'contact':'不应公开'}})
    def test_rule_based_candidate_pool_has_reasons_without_private_data(self):
        # Candidate ranking must be evaluated against a clean fixture, not the
        # developer's persisted local accounts and interaction history.
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    result=server.account_apply(db,{'action':'candidates','actor':'demo_candidate'})
                finally:
                    db.close()
                self.assertEqual(len(result['candidates']),1)
                match=result['candidates'][0]
                self.assertEqual(match['candidate']['id'],'demo_member')
                self.assertTrue(match['match_reasons'])
                self.assertTrue(match['premeet_topics'])
                self.assertNotIn('private',match)
                self.assertNotIn('income_assets',match['profile'])
                self.assertNotIn('score',match)
            finally:
                server.DB=original_db
    def test_frozen_accounts_are_hidden_and_cannot_start_or_continue_premeet(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    db.execute("UPDATE admin_account_state SET account_status='已冻结' WHERE user_id='demo_member'")
                    self.assertEqual(server.account_apply(db,{'action':'candidates','actor':'demo_candidate'})['candidates'],[])
                    with self.assertRaises(ValueError): server.request_premeet_room(db,'demo_candidate','demo_member')
                    db.execute("UPDATE admin_account_state SET account_status='正常' WHERE user_id='demo_member'")
                    room=server.request_premeet_room(db,'demo_candidate','demo_member')
                    db.execute("UPDATE admin_account_state SET account_status='已冻结' WHERE user_id='demo_member'")
                    with self.assertRaises(ValueError): server.authorize_bound_action(db,room,{'action':'message','actor':'demo_candidate'})
                finally: db.close()
            finally: server.DB=original_db
    def test_session_bound_account_can_revoke_and_delete_its_data(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    created=server.auth_apply(db,{'action':'local_register','nickname':'新会员','role':'member'})
                    actor=server.session_actor(db,created['session'])
                    self.assertEqual(actor,created['user']['id'])
                    with self.assertRaises(ValueError): server.account_apply(db,{'action':'revoke_premeet','actor':actor})
                    deleted=server.account_apply(db,{'action':'delete_account','actor':actor})
                    self.assertEqual(deleted['deleted_user'],actor)
                    with self.assertRaises(ValueError): server.session_actor(db,created['session'])
                finally: db.close()
            finally: server.DB=original_db
    def test_membership_is_an_entitlement_not_a_registration_role(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    created=server.auth_apply(db,{'action':'local_register','nickname':'普通用户','role':'member'})
                    actor=created['user']['id']
                    self.assertEqual(created['user']['account_type'],'user')
                    self.assertEqual(created['user']['role'],'candidate')
                    entitlement=server.set_membership_entitlement(db,actor,'active','体验会员',source='test')
                    self.assertTrue(entitlement['active'])
                    self.assertEqual(server.require_test_account(db,actor)['role'],'member')
                    self.assertTrue(server.match_preferences(db,actor)['premeet_enabled'])
                    self.assertIsNotNone(server.twin_profile(db,actor))
                finally: db.close()
            finally: server.DB=original_db
    def test_local_test_account_can_be_selected_and_logged_in_again(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    created=server.auth_apply(db,{'action':'local_register','nickname':'testboy'})
                    options=server.auth_apply(db,{'action':'local_accounts'})['accounts']
                    item=next(account for account in options if account['id']==created['user']['id'])
                    self.assertEqual(item['nickname'],'testboy')
                    resumed=server.auth_apply(db,{'action':'local_login','user_id':item['id']})
                    self.assertNotEqual(resumed['session'],created['session'])
                    self.assertEqual(server.session_actor(db,resumed['session']),item['id'])
                    self.assertEqual(server.account_apply(db,{'action':'onboarding','actor':item['id']})['data'],{})
                finally: db.close()
            finally: server.DB=original_db
    def test_recommendation_reads_onboarding_preferences_without_exposing_private_data(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    member={'birthday':'1993年1月1日','height':'175cm','education':'硕士','city':'江苏省·南京市·鼓楼区','housing':'有房','vehicle':'有车','marital':'未婚','relationshipGoal':'认真恋爱','occupation':'IT/互联网 / 工程师','onlyChild':'是','childrenPlan':'想要小孩'}
                    candidate={'birthday':'1995年1月1日','height':'165cm','education':'本科','city':'江苏省·南京市·建邺区','housing':'有房','vehicle':'没车','marital':'未婚','relationshipGoal':'认真恋爱','distance':'接受','ageRange':'30–35岁','heightRange':'170–180cm','prefEducation':'硕士','prefHousing':'有房','prefOccupation':['IT/互联网'],'prefOnlyChild':'希望','prefMarital':['未婚'],'prefChildren':'想要小孩','priorities':['年龄范围','最低学历','是否有房','是否独生','婚育情况']}
                    server.save_onboarding_data(db,'demo_member',member)
                    server.save_onboarding_data(db,'demo_candidate',candidate)
                    match=server.candidate_matches(db,'demo_candidate')['candidates'][0]
                    joined='；'.join(match['match_reasons'])
                    self.assertIn('年龄在你的期待范围内',joined)
                    self.assertIn('职业属于你关注的领域',joined)
                    self.assertGreaterEqual(match['priority_match_count'],3)
                    self.assertNotIn('birthday',match['profile'])
                    self.assertNotIn('onlyChild',match['profile'])
                finally: db.close()
            finally: server.DB=original_db
    def test_smart_search_updates_the_same_priority_data_used_by_recommendation(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    result=server.account_apply(db,{'actor':'demo_candidate','action':'save_search_priorities','priorities':['年龄范围','最低学历'],'note':'希望沟通坦诚'})
                    self.assertEqual(result['priorities'],['年龄范围','最低学历'])
                    saved=server.match_preferences(db,'demo_candidate')['onboarding']
                    self.assertEqual(saved['priorities'],['年龄范围','最低学历'])
                    self.assertEqual(saved['preferenceNote'],'希望沟通坦诚')
                finally: db.close()
            finally: server.DB=original_db
    def test_candidate_request_creates_bound_room_from_public_snapshots(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    room=server.request_premeet_room(db,'demo_candidate','demo_member')
                    repeated=server.request_premeet_room(db,'demo_candidate','demo_member')
                    self.assertEqual(room['id'],repeated['id'])
                    self.assertEqual(room['room_type'],'bound_premeet')
                    self.assertEqual(room['candidate_id'],'demo_candidate')
                    self.assertEqual(room['member_id'],'demo_member')
                    self.assertIn('南京',server.conversation_prompt(room))
                    self.assertNotIn('测试用私密地址',json.dumps(server.public(room),ensure_ascii=False))
                finally:
                    db.close()
            finally:
                server.DB=original_db
    def test_bound_room_separates_candidate_and_member_views(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    room=server.request_premeet_room(db,'demo_candidate','demo_member')
                    room['messages']=[{'role':'user','content':'候选真人原始提问'}]
                    room['owner_private_followups']=['会员需要补充的偏好','还有什么偏好需要补充']
                    candidate=server.room_response(db,room,'demo_candidate')
                    member=server.room_response(db,room,'demo_member')
                    self.assertEqual(candidate['viewer_role'],'candidate')
                    self.assertEqual(candidate['messages'][0]['content'],'候选真人原始提问')
                    self.assertNotIn('owner_private_followups',candidate)
                    self.assertEqual(member['viewer_role'],'member')
                    self.assertNotIn('messages',member)
                    self.assertEqual(member['private_calibration'][0]['label'],'有一项日常表达仍需要你的校准')
                    self.assertNotIn('会员需要补充的偏好',json.dumps(member,ensure_ascii=False))
                    with self.assertRaises(ValueError): server.room_response(db,room,'nobody')
                finally: db.close()
            finally: server.DB=original_db
    def test_bound_room_actions_follow_identity_not_browser_role(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    room=server.request_premeet_room(db,'demo_candidate','demo_member')
                    candidate={'action':'decision','actor':'demo_candidate','role':'owner','agree':True}
                    self.assertEqual(server.authorize_bound_action(db,room,candidate),'candidate')
                    self.assertEqual(candidate['role'],'me')
                    member={'action':'decision','actor':'demo_member','role':'me','agree':True}
                    self.assertEqual(server.authorize_bound_action(db,room,member),'member')
                    self.assertEqual(member['role'],'owner')
                    with self.assertRaises(ValueError): server.authorize_bound_action(db,room,{'action':'message','actor':'demo_member'})
                finally: db.close()
            finally: server.DB=original_db
    def test_member_gets_candidate_specific_end_reason(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    room=server.request_premeet_room(db,'demo_candidate','demo_member')
                    action={'action':'end','actor':'demo_candidate'}
                    server.authorize_bound_action(db,room,action);server.apply(room,'end',action)
                    self.assertEqual(server.room_response(db,room,'demo_candidate')['reason'],'你主动结束了预会面')
                    self.assertEqual(server.room_response(db,room,'demo_member')['reason'],'候选真人主动结束了预会面')
                finally: db.close()
            finally: server.DB=original_db
    def test_member_invitation_stays_waiting_until_candidate_accepts(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    room=server.invite_premeet_room(db,'demo_member','demo_candidate')
                    summary=server.member_room_summaries(db,'demo_member')['rooms'][0]
                    self.assertEqual(room['status'],'awaiting_candidate')
                    self.assertEqual(summary['status'],'awaiting_candidate')
                    self.assertIsNone(summary['started'])
                    self.assertEqual(summary['rounds'],0)
                finally: db.close()
            finally: server.DB=original_db
    def test_conversation_prompt_uses_current_member_identity_and_red_matchmaker_tip(self):
        room=self.room()
        room['member_profile_snapshot']={'nickname':'testboy'}
        prompt=server.conversation_prompt(room)
        self.assertIn('testboy授权的AI分身',prompt)
        self.assertNotIn('林予安确认',prompt)
        self.assertIn('AI 红娘本轮引导',prompt)
    def test_service_group_starts_after_both_consent_and_hides_reports(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    room=server.request_premeet_room(db,'demo_candidate','demo_member')
                    self.assertIsNone(server.ensure_service_group(db,room))
                    room.update(status='ready_for_handoff',decisions={'me':True,'owner':True})
                    group=server.ensure_service_group(db,room)
                    self.assertEqual(group['status'],'active')
                    server.save_service_group(db,group)
                    candidate=server.group_apply(db,{'id':group['id'],'actor':'demo_candidate','action':'safety_report','detail':'测试安全工单'})
                    member=server.group_apply(db,{'id':group['id'],'actor':'demo_member','action':'state'})
                    self.assertEqual(len(candidate['my_safety_reports']),1)
                    self.assertEqual(member['my_safety_reports'],[])
                    suggestion=server.group_apply(db,{'id':group['id'],'actor':'demo_member','action':'date_suggestion'})
                    self.assertIn('约',suggestion['date_suggestion'])
                finally: db.close()
            finally: server.DB=original_db
    def test_service_group_expires_after_seven_days(self):
        group={'status':'active','deadline':0,'events':[]}
        server.expire_service_group(group,now=1)
        self.assertEqual(group['status'],'expired')
    def test_member_can_calibrate_without_receiving_candidate_raw_question(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    room=server.request_premeet_room(db,'demo_candidate','demo_member')
                    room['owner_private_followups']=['你喜欢吃甜食吗？','你平时偏甜还是偏咸？']
                    db.execute('UPDATE rooms SET data=? WHERE id=?',(json.dumps(room,ensure_ascii=False),room['id']))
                    visible=server.room_response(db,room,'demo_member')
                    item=visible['private_calibration'][0]
                    self.assertNotIn('甜食',json.dumps(visible,ensure_ascii=False))
                    updated=server.calibrate_topic(db,'demo_member',room['id'],item['id'],'allow','我不排斥甜食，但更看具体场景。')
                    self.assertEqual(updated['data']['topic_answers'][item['label']],'我不排斥甜食，但更看具体场景。')
                finally: db.close()
            finally: server.DB=original_db
    def test_priority_topics_are_limited_and_safely_shared_with_candidate(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    profile=server.twin_profile(db,'demo_member')
                    data=profile['data']; data['priority_topics']=server.topic_suggestions('first')[:3]
                    server.save_twin_profile(db,'demo_member',data,profile['version'])
                    room=server.request_premeet_room(db,'demo_candidate','demo_member')
                    candidate=server.room_response(db,room,'demo_candidate')
                    self.assertEqual(len(candidate['premeet_priority_topics']),3)
                    self.assertNotIn('twin_profile',candidate)
                    self.assertIn('优先议题',server.conversation_prompt(room))
                    current=server.twin_profile(db,'demo_member')
                    current['data']['priority_topics']=server.topic_suggestions('second')[:4]
                    with self.assertRaises(ValueError): server.save_twin_profile(db,'demo_member',current['data'],current['version'])
                finally: db.close()
            finally: server.DB=original_db
    def test_member_exception_blocks_next_reply_after_twin_refresh(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    room=server.request_premeet_room(db,'demo_candidate','demo_member');room['mode']='demo'
                    profile=server.twin_profile(db,'demo_member')
                    data=profile['data'];data['answer_policy']['never_answer']=['收入与资产情况']
                    server.save_twin_profile(db,'demo_member',data,profile['version'])
                    server.refresh_room_twin(db,room)
                    server.apply(room,'message',{'text':'你的收入大概是多少？'})
                    self.assertIn('留到之后由真人交流',room['messages'][-1]['content'])
                    self.assertEqual(room['reply_sources'][-1]['source'],'member_exception')
                finally: db.close()
            finally: server.DB=original_db
    def test_conversation_guidance_changes_with_rounds_without_blocking_free_chat(self):
        room=self.room();room['twin_profile']={'priority_topics':[{'label':'未来城市安排','category':'城市规划'}]}
        opening=server.guided_prompts(room)
        self.assertEqual(opening['stage'],'轻松破冰')
        self.assertIn('未来城市安排',opening['prompts'][0])
        room['rounds']=13
        self.assertEqual(server.guided_prompts(room)['stage'],'关系节奏与价值取舍')
        self.assertIn('不要为了完成阶段强行转话题',server.conversation_prompt(room))
    def test_unsafe_content_is_redirected_without_counting_as_a_special_flow(self):
        room=self.room();server.apply(room,'message',{'text':'要不要一起投资项目，稳赚？'})
        self.assertIn('不适合在这里继续',room['messages'][-1]['content'])
        self.assertEqual(room['reply_sources'][-1]['source'],'safety_redirect')
    def test_calibration_is_low_frequency_and_aggregated_by_topic(self):
        room=self.room();room['id']='low-frequency-room'
        room['owner_private_followups']=['你喜欢吃甜食吗？']
        self.assertEqual(server.calibration_insights(room),[])
        room['owner_private_followups'].append('你平时偏甜还是偏咸？')
        insights=server.calibration_insights(room)
        self.assertEqual(len(insights),1)
        self.assertNotIn('甜食',json.dumps(insights,ensure_ascii=False))
        room['calibration_dismissed_topics']=[insights[0]['label']]
        self.assertEqual(server.calibration_insights(room),[])
    def test_discovery_feedback_moves_like_and_hides_dislike(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    liked=server.account_apply(db,{'actor':'demo_candidate','action':'recommendation_feedback','target_id':'demo_member','status':'liked'})
                    self.assertEqual(liked['status'],'liked')
                    favorites=server.account_apply(db,{'actor':'demo_candidate','action':'likes'})
                    self.assertEqual(favorites['likes'][0]['user']['id'],'demo_member')
                    server.account_apply(db,{'actor':'demo_candidate','action':'recommendation_feedback','target_id':'demo_member','status':'disliked'})
                    self.assertEqual(server.candidate_matches(db,'demo_candidate')['candidates'],[])
                finally: db.close()
            finally: server.DB=original_db
    def test_relationship_signals_keep_direction_and_only_surface_mutual_interest(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    server.record_relationship_signal(db,'demo_candidate','demo_member','liked','test')
                    one_way=server.relationship_signal_summary(db,'demo_candidate','demo_member')
                    self.assertFalse(one_way['mutual_interest'])
                    self.assertEqual(one_way['reasons'],[])
                    server.record_relationship_signal(db,'demo_member','demo_candidate','liked','test')
                    mutual=server.relationship_signal_summary(db,'demo_candidate','demo_member')
                    self.assertTrue(mutual['mutual_interest'])
                    self.assertIn('双方都已表达进一步了解的意愿',mutual['reasons'])
                    self.assertNotIn('disliked',json.dumps(mutual,ensure_ascii=False))
                finally: db.close()
            finally: server.DB=original_db
    def test_premeet_request_and_invite_write_interaction_signals(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    requested=server.request_premeet_room(db,'demo_candidate','demo_member')
                    events=db.execute("SELECT signal FROM relationship_signals WHERE actor_id='demo_candidate' AND target_id='demo_member'").fetchall()
                    self.assertIn('premeet_requested',{item['signal'] for item in events})
                    self.assertEqual(requested['room_type'],'bound_premeet')
                finally: db.close()
            finally: server.DB=original_db
    def test_curated_candidates_return_reference_and_explanation_without_internal_score(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    result=server.account_apply(db,{'actor':'demo_candidate','action':'curated'})
                    self.assertEqual(result['candidates'][0]['candidate']['id'],'demo_member')
                    card=result['candidates'][0]
                    self.assertGreaterEqual(card['match_reference'],60)
                    self.assertLessEqual(card['match_reference'],96)
                    self.assertGreaterEqual(card['matched_condition_count'],1)
                    self.assertTrue(card['summary'])
                    self.assertNotIn('_sort_score',card)
                    self.assertNotIn('private',json.dumps(card,ensure_ascii=False))
                finally: db.close()
            finally: server.DB=original_db
    def test_core_relationship_question_bank_is_fixed_versioned_and_balanced(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    questionnaire=server.relationship_questionnaire(db,'demo_member')
                    self.assertEqual(questionnaire['total_count'],11)
                    self.assertEqual(questionnaire['answered_count'],0)
                    dimensions={item['dimension'] for item in questionnaire['questions']}
                    self.assertEqual(sum(item['dimension']=='关系推进节奏' for item in questionnaire['questions']),2)
                    self.assertEqual(sum(item['dimension']=='分歧与修复' for item in questionnaire['questions']),3)
                    self.assertEqual(sum(item['dimension']=='亲密与个人空间' for item in questionnaire['questions']),2)
                    self.assertEqual(sum(item['dimension']=='压力支持与协作' for item in questionnaire['questions']),2)
                    self.assertEqual(sum(item['dimension']=='家庭边界与生活决策' for item in questionnaire['questions']),2)
                    self.assertEqual(len(dimensions),5)
                    governed=db.execute('SELECT version,status,theory_source,use_scope FROM relationship_question_bank').fetchall()
                    self.assertTrue(all(item['version']==1 and item['status']=='active' and item['theory_source'] and item['use_scope'] for item in governed))
                finally: db.close()
            finally: server.DB=original_db
    def test_relationship_answers_build_a_non_diagnostic_twin_expression_packet(self):
        original_db=server.DB
        with tempfile.TemporaryDirectory() as folder:
            server.DB=Path(folder)/'test.sqlite3'
            try:
                db=server.connect()
                try:
                    saved=server.save_relationship_questionnaire(db,'demo_member',{
                        'pace_define':'steady','conflict_timing':'cool_then_talk','space_weekend':'balance','stress_support':'ask','family_boundary':'couple_decide'})
                    profile=saved['twin']['data']['relationship_profile']
                    self.assertEqual(profile['answered_count'],5)
                    self.assertIn('先稳定相处',profile['summary'])
                    self.assertIn('分歧与修复',{item['dimension'] for item in profile['dimensions']})
                    self.assertEqual(saved['questionnaire']['answered_count'],5)
                    with self.assertRaises(ValueError): server.save_relationship_questionnaire(db,'demo_member',{'pace_define':'not-an-option'})
                finally: db.close()
            finally: server.DB=original_db
if __name__=='__main__':unittest.main()
