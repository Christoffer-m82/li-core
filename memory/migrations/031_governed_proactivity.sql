BEGIN;

DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.30') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 031 requires applied schema 0.30';
 END IF;
 IF EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.31') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Schema version 0.31 is already claimed';
 END IF;
END $$;

ALTER TABLE li_runtime_data.rhythm_definitions
 DROP CONSTRAINT rhythm_definitions_mode_check,
 ADD COLUMN local_time TIME NOT NULL DEFAULT '09:00',
 ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT FALSE,
 ADD COLUMN quiet_hours_start TIME,
 ADD COLUMN quiet_hours_end TIME,
 ADD COLUMN last_run TIMESTAMPTZ,
 ADD COLUMN next_run TIMESTAMPTZ,
 ADD COLUMN last_result TEXT CHECK(last_result IN ('generated','empty','suppressed','failed')),
 ADD COLUMN last_run_key TEXT,
 ADD COLUMN stood_down_until TIMESTAMPTZ,
 ADD CONSTRAINT rhythm_definitions_mode_check CHECK(mode IN ('disabled','preview_only','approved')),
 ADD CONSTRAINT approved_before_enabled CHECK(NOT enabled OR mode='approved');
UPDATE li_runtime_data.rhythm_definitions SET local_time=CASE key
 WHEN 'morning' THEN '07:30'::TIME WHEN 'friday' THEN '16:00'::TIME ELSE '09:00'::TIME END;

ALTER TABLE li_runtime_data.open_loops
 ADD COLUMN commitment_kind TEXT NOT NULL DEFAULT 'self' CHECK(commitment_kind IN ('self','other_person')),
 ADD COLUMN suppressed_until TIMESTAMPTZ,
 ADD COLUMN suppression_reason TEXT CHECK(suppression_reason IN ('not_now','later','leave_it')),
 ADD COLUMN blocker_prompted_at TIMESTAMPTZ;

CREATE TABLE li_runtime_data.proactivity_suppressions(
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 category TEXT NOT NULL, suppression_kind TEXT NOT NULL CHECK(suppression_kind IN ('not_now','later','leave_it','category')),
 suppressed_until TIMESTAMPTZ, active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(owner_user_id,category)
);
CREATE TABLE li_runtime_data.rhythm_runs(
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 rhythm_key TEXT NOT NULL REFERENCES li_runtime_data.rhythm_definitions(key), run_key TEXT NOT NULL,
 scheduled_for TIMESTAMPTZ NOT NULL, status TEXT NOT NULL CHECK(status IN ('claimed','generated','empty','suppressed','failed')),
 result_metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(result_metadata)='object'),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ,
 UNIQUE(owner_user_id,rhythm_key,run_key)
);
CREATE TABLE li_runtime_data.proactive_briefs(
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 rhythm_run_id UUID NOT NULL UNIQUE REFERENCES li_runtime_data.rhythm_runs(id), title TEXT NOT NULL,
 neutral_preview TEXT NOT NULL DEFAULT 'A new private Li brief is ready.', content JSONB NOT NULL CHECK(jsonb_typeof(content)='object'),
 delivery_status TEXT NOT NULL DEFAULT 'delivered' CHECK(delivery_status IN ('pending','delivered','failed')),
 delivered_at TIMESTAMPTZ, read_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE li_runtime_data.proactivity_events(
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 event_type TEXT NOT NULL CHECK(event_type IN ('run','brief_generated','brief_delivered','brief_read','suppressed','loop_raised','loop_postponed','loop_closed','duplicate_prevented')),
 rhythm_key TEXT, open_loop_id UUID, metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(metadata)='object'),
 occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX proactive_briefs_inbox_idx ON li_runtime_data.proactive_briefs(owner_user_id,read_at,created_at DESC);

ALTER TABLE li_runtime_data.proactivity_suppressions ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.rhythm_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.proactive_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.proactivity_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY proactivity_suppression_function_access ON li_runtime_data.proactivity_suppressions FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY rhythm_run_function_access ON li_runtime_data.rhythm_runs FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY proactive_brief_function_access ON li_runtime_data.proactive_briefs FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY proactivity_event_function_access ON li_runtime_data.proactivity_events FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT,UPDATE ON li_runtime_data.proactivity_suppressions,li_runtime_data.rhythm_runs,li_runtime_data.proactive_briefs,li_runtime_data.proactivity_events TO li_memory_function_owner;
GRANT USAGE,SELECT ON SEQUENCE li_runtime_data.proactivity_events_id_seq TO li_memory_function_owner;

CREATE TEMP TABLE migration_031_authority_state(migration_role NAME,added_owner BOOLEAN,added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_031_authority_state SELECT CURRENT_USER,
 NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
 NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_031_authority_state) THEN EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I',(SELECT migration_role FROM migration_031_authority_state)); END IF;
 IF (SELECT added_create FROM migration_031_authority_state) THEN EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner'; END IF;
END $$;
SET LOCAL ROLE li_memory_function_owner;

DROP FUNCTION li_api.create_open_loop(TEXT,TEXT,UUID,UUID,TEXT,TIMESTAMPTZ,TEXT,BOOLEAN,BOOLEAN);
CREATE FUNCTION li_api.create_open_loop(p_summary TEXT,p_owed TEXT,p_conversation UUID,p_request UUID,p_next TEXT,p_due TIMESTAMPTZ,p_urgency TEXT,p_approved BOOLEAN,p_sensitive BOOLEAN,p_kind TEXT)
RETURNS SETOF li_runtime_data.open_loops LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_id UUID:=gen_random_uuid(); BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 IF p_sensitive AND NOT p_approved THEN RAISE EXCEPTION 'Sensitive commitment requires approval'; END IF;
 IF p_kind NOT IN ('self','other_person') THEN RAISE EXCEPTION 'Invalid commitment kind'; END IF;
 IF p_conversation IS NOT NULL AND NOT EXISTS(SELECT 1 FROM li_conversation.conversations c WHERE c.id=p_conversation AND c.owner_user_id=v_user) THEN RAISE EXCEPTION 'Conversation not found'; END IF;
 INSERT INTO li_runtime_data.open_loops(id,owner_user_id,commitment_summary,owed_to,source_conversation_id,source_request_id,next_action,due_at,urgency,commitment_kind)
 VALUES(v_id,v_user,p_summary,p_owed,p_conversation,p_request,p_next,p_due,p_urgency,p_kind);
 RETURN QUERY SELECT * FROM li_runtime_data.open_loops WHERE id=v_id; END $$;
CREATE FUNCTION li_api.suppress_open_loop(p_id UUID,p_action TEXT,p_until TIMESTAMPTZ) RETURNS SETOF li_runtime_data.open_loops LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ BEGIN
 IF p_action NOT IN ('not_now','later','leave_it') OR (p_action='later' AND p_until IS NULL) THEN RAISE EXCEPTION 'Invalid suppression'; END IF;
 UPDATE li_runtime_data.open_loops o SET suppression_reason=p_action,suppressed_until=CASE WHEN p_action='not_now' THEN NOW()+INTERVAL '1 day' WHEN p_action='later' THEN p_until ELSE 'infinity'::TIMESTAMPTZ END
 WHERE o.id=p_id AND o.status<>'closed' AND o.owner_user_id=(SELECT id FROM li_memory.users WHERE user_key='christoffer' AND status='active');
 IF NOT FOUND THEN RAISE EXCEPTION 'Open loop not found'; END IF;
 RETURN QUERY SELECT o.* FROM li_runtime_data.open_loops o WHERE o.id=p_id; END $$;
CREATE OR REPLACE FUNCTION li_api.transition_open_loop(p_id UUID,p_transition TEXT) RETURNS SETOF li_runtime_data.open_loops LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ BEGIN
 IF p_transition NOT IN ('postpone','raise','close') THEN RAISE EXCEPTION 'Invalid open-loop transition'; END IF;
 UPDATE li_runtime_data.open_loops o SET status=CASE WHEN p_transition='postpone' THEN 'postponed' WHEN p_transition='close' THEN 'closed' ELSE 'open' END,
  postponement_count=postponement_count+CASE WHEN p_transition='postpone' THEN 1 ELSE 0 END,
  blocker_prompted_at=CASE WHEN p_transition='postpone' AND postponement_count+1>=3 AND blocker_prompted_at IS NULL THEN NOW() ELSE blocker_prompted_at END,
  last_raised_at=CASE WHEN p_transition='raise' THEN NOW() ELSE last_raised_at END,
  closed_at=CASE WHEN p_transition='close' THEN NOW() ELSE NULL END
 WHERE o.id=p_id AND o.owner_user_id=(SELECT u.id FROM li_memory.users u WHERE u.user_key='christoffer' AND u.status='active');
 IF NOT FOUND THEN RAISE EXCEPTION 'Open loop not found'; END IF;
 RETURN QUERY SELECT o.* FROM li_runtime_data.open_loops o WHERE o.id=p_id; END $$;
CREATE FUNCTION li_api.set_proactivity_suppression(p_category TEXT,p_action TEXT,p_until TIMESTAMPTZ)
RETURNS SETOF li_runtime_data.proactivity_suppressions LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; BEGIN
 IF p_category!~'^[a-z_]{2,40}$' OR p_action NOT IN ('not_now','later','leave_it') OR (p_action='later' AND p_until IS NULL) THEN RAISE EXCEPTION 'Invalid category suppression'; END IF;
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active';
 INSERT INTO li_runtime_data.proactivity_suppressions(owner_user_id,category,suppression_kind,suppressed_until)
 VALUES(v_user,p_category,p_action,CASE WHEN p_action='not_now' THEN NOW()+INTERVAL '1 day' WHEN p_action='later' THEN p_until ELSE 'infinity'::TIMESTAMPTZ END)
 ON CONFLICT(owner_user_id,category) DO UPDATE SET suppression_kind=EXCLUDED.suppression_kind,suppressed_until=EXCLUDED.suppressed_until,active=TRUE,created_at=NOW();
 RETURN QUERY SELECT * FROM li_runtime_data.proactivity_suppressions WHERE owner_user_id=v_user AND category=p_category; END $$;
CREATE FUNCTION li_api.list_proactivity_suppressions() RETURNS SETOF li_runtime_data.proactivity_suppressions LANGUAGE sql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ SELECT s.* FROM li_runtime_data.proactivity_suppressions s JOIN li_memory.users u ON u.id=s.owner_user_id WHERE u.user_key='christoffer' AND s.active AND (s.suppressed_until IS NULL OR s.suppressed_until>NOW()) $$;

CREATE FUNCTION li_api.list_rhythm_states() RETURNS SETOF li_runtime_data.rhythm_definitions LANGUAGE sql SECURITY DEFINER
SET search_path=li_runtime_data,pg_catalog,pg_temp AS $$ SELECT * FROM li_runtime_data.rhythm_definitions ORDER BY key $$;
CREATE FUNCTION li_api.configure_rhythm(p_key TEXT,p_enabled BOOLEAN,p_timezone TEXT,p_local_time TIME,p_next TIMESTAMPTZ,p_approved BOOLEAN)
RETURNS SETOF li_runtime_data.rhythm_definitions LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,pg_catalog,pg_temp AS $$ BEGIN
 IF p_enabled AND NOT p_approved THEN RAISE EXCEPTION 'Explicit rhythm activation approval required'; END IF;
 UPDATE li_runtime_data.rhythm_definitions SET enabled=p_enabled,mode=CASE WHEN p_enabled THEN 'approved' ELSE 'disabled' END,
  timezone=p_timezone,local_time=p_local_time,next_run=CASE WHEN p_enabled THEN p_next ELSE NULL END WHERE key=p_key;
 IF NOT FOUND THEN RAISE EXCEPTION 'Unknown rhythm'; END IF;
 RETURN QUERY SELECT * FROM li_runtime_data.rhythm_definitions WHERE key=p_key; END $$;
CREATE FUNCTION li_api.claim_rhythm_run(p_key TEXT,p_run_key TEXT,p_scheduled TIMESTAMPTZ)
RETURNS TABLE(run_id UUID,claimed BOOLEAN,state TEXT) LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_id UUID; v_state li_runtime_data.rhythm_definitions%ROWTYPE; BEGIN
 SELECT * INTO v_state FROM li_runtime_data.rhythm_definitions WHERE key=p_key FOR UPDATE;
 IF NOT FOUND OR NOT v_state.enabled OR v_state.mode<>'approved' THEN RETURN QUERY SELECT NULL::UUID,FALSE,'disabled'::TEXT; RETURN; END IF;
 IF v_state.stood_down_until IS NOT NULL AND v_state.stood_down_until>NOW() THEN RETURN QUERY SELECT NULL::UUID,FALSE,'suppressed'::TEXT; RETURN; END IF;
 IF v_state.quiet_hours_start IS NOT NULL AND v_state.quiet_hours_end IS NOT NULL AND
   (CASE WHEN v_state.quiet_hours_start<v_state.quiet_hours_end THEN
      (p_scheduled AT TIME ZONE v_state.timezone)::TIME>=v_state.quiet_hours_start AND (p_scheduled AT TIME ZONE v_state.timezone)::TIME<v_state.quiet_hours_end
    ELSE (p_scheduled AT TIME ZONE v_state.timezone)::TIME>=v_state.quiet_hours_start OR (p_scheduled AT TIME ZONE v_state.timezone)::TIME<v_state.quiet_hours_end END)
 THEN RETURN QUERY SELECT NULL::UUID,FALSE,'suppressed'::TEXT; RETURN; END IF;
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 INSERT INTO li_runtime_data.rhythm_runs(owner_user_id,rhythm_key,run_key,scheduled_for,status) VALUES(v_user,p_key,p_run_key,p_scheduled,'claimed')
 ON CONFLICT(owner_user_id,rhythm_key,run_key) DO NOTHING RETURNING id INTO v_id;
 IF v_id IS NULL THEN INSERT INTO li_runtime_data.proactivity_events(owner_user_id,event_type,rhythm_key,metadata) VALUES(v_user,'duplicate_prevented',p_key,jsonb_build_object('run_key',p_run_key)); END IF;
 RETURN QUERY SELECT v_id,v_id IS NOT NULL,CASE WHEN v_id IS NULL THEN 'duplicate' ELSE 'claimed' END; END $$;
CREATE FUNCTION li_api.complete_rhythm_run(p_id UUID,p_status TEXT,p_title TEXT,p_content JSONB,p_sensitive BOOLEAN,p_next TIMESTAMPTZ)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,pg_catalog,pg_temp AS $$ DECLARE r li_runtime_data.rhythm_runs%ROWTYPE; v_brief UUID; BEGIN
 SELECT * INTO r FROM li_runtime_data.rhythm_runs WHERE id=p_id AND status='claimed' FOR UPDATE;
 IF NOT FOUND OR p_status NOT IN ('generated','empty','suppressed','failed') THEN RAISE EXCEPTION 'Invalid rhythm completion'; END IF;
 UPDATE li_runtime_data.rhythm_runs SET status=p_status,completed_at=NOW() WHERE id=p_id;
 UPDATE li_runtime_data.rhythm_definitions SET last_run=NOW(),last_result=p_status,last_run_key=r.run_key,next_run=p_next WHERE key=r.rhythm_key;
 IF p_status='generated' THEN INSERT INTO li_runtime_data.proactive_briefs(owner_user_id,rhythm_run_id,title,neutral_preview,content,delivery_status,delivered_at)
  VALUES(r.owner_user_id,r.id,p_title,CASE WHEN p_sensitive THEN 'A new private Li brief is ready.' ELSE p_title END,p_content,'delivered',NOW()) RETURNING id INTO v_brief;
  INSERT INTO li_runtime_data.proactivity_events(owner_user_id,event_type,rhythm_key,metadata) VALUES(r.owner_user_id,'brief_delivered',r.rhythm_key,jsonb_build_object('brief_id',v_brief)); END IF;
 RETURN v_brief; END $$;
CREATE FUNCTION li_api.list_proactive_briefs(p_limit INTEGER DEFAULT 50) RETURNS TABLE(id UUID,rhythm_key TEXT,title TEXT,neutral_preview TEXT,delivery_status TEXT,created_at TIMESTAMPTZ,read_at TIMESTAMPTZ,content JSONB) LANGUAGE sql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ SELECT b.id,r.rhythm_key,b.title,b.neutral_preview,b.delivery_status,b.created_at,b.read_at,b.content FROM li_runtime_data.proactive_briefs b JOIN li_runtime_data.rhythm_runs r ON r.id=b.rhythm_run_id JOIN li_memory.users u ON u.id=b.owner_user_id WHERE u.user_key='christoffer' ORDER BY b.created_at DESC LIMIT LEAST(GREATEST(p_limit,1),100) $$;
CREATE FUNCTION li_api.mark_proactive_brief_read(p_id UUID) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active'; UPDATE li_runtime_data.proactive_briefs SET read_at=COALESCE(read_at,NOW()) WHERE id=p_id AND owner_user_id=v_user; RETURN FOUND; END $$;

RESET ROLE;
REVOKE ALL ON FUNCTION li_api.create_open_loop(TEXT,TEXT,UUID,UUID,TEXT,TIMESTAMPTZ,TEXT,BOOLEAN,BOOLEAN,TEXT),li_api.suppress_open_loop(UUID,TEXT,TIMESTAMPTZ),li_api.set_proactivity_suppression(TEXT,TEXT,TIMESTAMPTZ),li_api.list_proactivity_suppressions(),li_api.list_rhythm_states(),li_api.configure_rhythm(TEXT,BOOLEAN,TEXT,TIME,TIMESTAMPTZ,BOOLEAN),li_api.claim_rhythm_run(TEXT,TEXT,TIMESTAMPTZ),li_api.complete_rhythm_run(UUID,TEXT,TEXT,JSONB,BOOLEAN,TIMESTAMPTZ),li_api.list_proactive_briefs(INTEGER),li_api.mark_proactive_brief_read(UUID) FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_theo,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.create_open_loop(TEXT,TEXT,UUID,UUID,TEXT,TIMESTAMPTZ,TEXT,BOOLEAN,BOOLEAN,TEXT),li_api.suppress_open_loop(UUID,TEXT,TIMESTAMPTZ),li_api.set_proactivity_suppression(TEXT,TEXT,TIMESTAMPTZ),li_api.list_proactivity_suppressions(),li_api.list_rhythm_states(),li_api.configure_rhythm(TEXT,BOOLEAN,TEXT,TIME,TIMESTAMPTZ,BOOLEAN),li_api.claim_rhythm_run(TEXT,TEXT,TIMESTAMPTZ),li_api.complete_rhythm_run(UUID,TEXT,TEXT,JSONB,BOOLEAN,TIMESTAMPTZ),li_api.list_proactive_briefs(INTEGER),li_api.mark_proactive_brief_read(UUID) TO li_memory_api;
REVOKE ALL PRIVILEGES ON li_runtime_data.proactivity_suppressions,li_runtime_data.rhythm_runs,li_runtime_data.proactive_briefs,li_runtime_data.proactivity_events FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
DO $$ BEGIN
 IF (SELECT added_create FROM migration_031_authority_state) THEN EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner'; END IF;
 IF (SELECT added_owner FROM migration_031_authority_state) THEN EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I',(SELECT migration_role FROM migration_031_authority_state)); END IF;
 IF NOT pg_catalog.has_function_privilege('li_backend_runtime','li_api.claim_rhythm_run(text,text,timestamptz)','EXECUTE') THEN RAISE EXCEPTION 'Backend runtime lost proactivity execution'; END IF;
 IF pg_catalog.has_function_privilege('li_artifact_retention','li_api.claim_rhythm_run(text,text,timestamptz)','EXECUTE') THEN RAISE EXCEPTION 'Retention runtime gained proactivity execution'; END IF;
END $$;
INSERT INTO li_memory.schema_versions(version,description) VALUES('0.31','Governed scheduler state, idempotent rhythm runs, proactive inbox, and suppression metadata');
COMMIT;
