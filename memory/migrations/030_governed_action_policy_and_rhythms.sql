BEGIN;

DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.29') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 030 requires applied schema 0.29';
 END IF;
 IF EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.30') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Schema version 0.30 is already claimed';
 END IF;
END $$;

CREATE TABLE li_runtime_data.action_policy_versions(
 version INTEGER PRIMARY KEY CHECK(version>0), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 policy JSONB NOT NULL CHECK(jsonb_typeof(policy)='object'), source TEXT NOT NULL CHECK(source IN ('baseline','approved_proposal','rollback')),
 source_proposal_id UUID, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), superseded_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX one_effective_action_policy ON li_runtime_data.action_policy_versions((owner_user_id)) WHERE superseded_at IS NULL;
CREATE TABLE li_runtime_data.action_policy_proposals(
 id UUID PRIMARY KEY, owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), base_version INTEGER NOT NULL,
 proposed_policy JSONB NOT NULL CHECK(jsonb_typeof(proposed_policy)='object'), summary TEXT NOT NULL CHECK(length(summary) BETWEEN 1 AND 1000),
 state TEXT NOT NULL DEFAULT 'proposed' CHECK(state IN ('proposed','approved','rejected','stale')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), resolved_at TIMESTAMPTZ
);
CREATE TABLE li_runtime_data.action_policy_events(
 event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 proposal_id UUID, actor TEXT NOT NULL CHECK(actor IN ('li','owner','system')), event_type TEXT NOT NULL,
 from_version INTEGER, to_version INTEGER, occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE li_runtime_data.rhythm_definitions(
 key TEXT PRIMARY KEY CHECK(key IN ('morning','friday','monthly','quarterly','annual')), label TEXT NOT NULL,
 cadence TEXT NOT NULL, timezone TEXT NOT NULL DEFAULT 'Europe/Berlin', mode TEXT NOT NULL DEFAULT 'preview_only'
  CHECK(mode IN ('disabled','preview_only')), external_mutations_permitted BOOLEAN NOT NULL DEFAULT FALSE CHECK(NOT external_mutations_permitted)
);
CREATE TABLE li_runtime_data.open_loops(
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 commitment_summary TEXT NOT NULL CHECK(length(commitment_summary) BETWEEN 1 AND 500), owed_to TEXT CHECK(length(owed_to)<=200),
 source_conversation_id UUID REFERENCES li_conversation.conversations(id) ON DELETE SET NULL, source_request_id UUID,
 next_action TEXT NOT NULL CHECK(length(next_action) BETWEEN 1 AND 500), due_at TIMESTAMPTZ,
 urgency TEXT NOT NULL DEFAULT 'normal' CHECK(urgency IN ('low','normal','high')), last_raised_at TIMESTAMPTZ,
 postponement_count INTEGER NOT NULL DEFAULT 0 CHECK(postponement_count>=0), status TEXT NOT NULL DEFAULT 'open'
  CHECK(status IN ('open','postponed','closed')), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), closed_at TIMESTAMPTZ
);
CREATE INDEX open_loops_due_idx ON li_runtime_data.open_loops(due_at) WHERE status<>'closed';

ALTER TABLE li_runtime_data.action_policy_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.action_policy_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.action_policy_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.rhythm_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.open_loops ENABLE ROW LEVEL SECURITY;
CREATE POLICY policy_version_function_access ON li_runtime_data.action_policy_versions FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY policy_proposal_function_access ON li_runtime_data.action_policy_proposals FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY policy_event_function_access ON li_runtime_data.action_policy_events FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY rhythm_function_access ON li_runtime_data.rhythm_definitions FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY open_loop_function_access ON li_runtime_data.open_loops FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT,UPDATE ON li_runtime_data.action_policy_versions,li_runtime_data.action_policy_proposals,
 li_runtime_data.rhythm_definitions,li_runtime_data.open_loops TO li_memory_function_owner;
GRANT SELECT,INSERT ON li_runtime_data.action_policy_events TO li_memory_function_owner;
GRANT USAGE,SELECT ON SEQUENCE li_runtime_data.action_policy_events_event_id_seq TO li_memory_function_owner;

INSERT INTO li_runtime_data.rhythm_definitions(key,label,cadence) VALUES
 ('morning','Morning review','weekdays 07:30'),('friday','Friday review','Friday 16:00'),
 ('monthly','Monthly review','first day 09:00'),('quarterly','Quarterly review','quarter start 09:00'),
 ('annual','Annual review','January 2 09:00');
INSERT INTO li_runtime_data.action_policy_versions(version,owner_user_id,policy,source)
SELECT 1,u.id,'{"schema_version":"1.0","policy_version":1,"specialist_action_authority":"none","categories":[
 {"category":"calendar","action_types":["calendar.create"],"approval_required":true,"auto_execution_permitted":false},
 {"category":"tasks","action_types":["task.create","task.complete","task.cancel"],"approval_required":true,"auto_execution_permitted":false},
 {"category":"email_drafts","action_types":["email.create_draft"],"approval_required":true,"auto_execution_permitted":false,"irreversibility":"reversible"},
 {"category":"registry_governance","action_types":["governance.execute"],"autonomy_level":"propose_only","approval_required":true,"owner_confirmation_required":true,"auto_execution_permitted":false,"irreversibility":"high","sensitivity":["employment"]},
 {"category":"money","action_types":["money.transact"],"autonomy_level":"propose_only","approval_required":true,"auto_execution_permitted":false,"known_vendor_required":true,"irreversibility":"high"},
 {"category":"legal_tax_employment","action_types":["legal.submit","tax.submit","employment.change"],"autonomy_level":"propose_only","approval_required":true,"owner_confirmation_required":true,"auto_execution_permitted":false,"irreversibility":"high","sensitivity":["legal","tax","employment"]},
 {"category":"third_party_family","action_types":["third_party.commit"],"autonomy_level":"propose_only","approval_required":true,"owner_confirmation_required":true,"auto_execution_permitted":false,"irreversibility":"high"}
 ],"freshness_evidence":{"enabled":false,"schema_version":"future-1","specialist_overrides":{}}}'::jsonb,'baseline'
FROM li_memory.users u WHERE u.user_key='christoffer' AND u.status='active';

CREATE TEMP TABLE migration_030_authority_state(added_owner BOOLEAN,added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_030_authority_state SELECT NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
 NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_030_authority_state) THEN EXECUTE 'GRANT li_memory_function_owner TO postgres'; END IF;
 IF (SELECT added_create FROM migration_030_authority_state) THEN EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner'; END IF;
END $$;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.get_action_policy_overview() RETURNS JSONB LANGUAGE sql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
 SELECT jsonb_build_object('effective_policy',v.policy,'history',COALESCE((SELECT jsonb_agg(jsonb_build_object(
  'version',h.version,'source',h.source,'created_at',h.created_at,'superseded_at',h.superseded_at) ORDER BY h.version DESC)
  FROM li_runtime_data.action_policy_versions h WHERE h.owner_user_id=v.owner_user_id),'[]'::jsonb),
  'pending_proposals',COALESCE((SELECT jsonb_agg(jsonb_build_object('proposal_id',p.id,'base_version',p.base_version,
  'summary',p.summary,'state',p.state,'created_at',p.created_at)) FROM li_runtime_data.action_policy_proposals p
  WHERE p.owner_user_id=v.owner_user_id AND p.state='proposed'),'[]'::jsonb))
 FROM li_runtime_data.action_policy_versions v JOIN li_memory.users u ON u.id=v.owner_user_id
 WHERE u.user_key='christoffer' AND u.status='active' AND v.superseded_at IS NULL LIMIT 1
$$;

CREATE FUNCTION li_api.propose_action_policy_change(p_id UUID,p_base INTEGER,p_policy JSONB,p_summary TEXT)
RETURNS TABLE(proposal_id UUID,state TEXT,base_version INTEGER) LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_current INTEGER;
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 SELECT version INTO v_current FROM li_runtime_data.action_policy_versions WHERE owner_user_id=v_user AND superseded_at IS NULL;
 IF p_base<>v_current OR jsonb_typeof(p_policy)<>'object' OR length(p_summary) NOT BETWEEN 1 AND 1000 THEN RAISE EXCEPTION 'Invalid or stale policy proposal'; END IF;
 IF COALESCE((p_policy->>'policy_version')::INTEGER,0)<>p_base+1 THEN RAISE EXCEPTION 'Proposed policy version must advance exactly once'; END IF;
 INSERT INTO li_runtime_data.action_policy_proposals(id,owner_user_id,base_version,proposed_policy,summary)
 VALUES(p_id,v_user,p_base,p_policy,p_summary);
 INSERT INTO li_runtime_data.action_policy_events(owner_user_id,proposal_id,actor,event_type,from_version)
 VALUES(v_user,p_id,'li','proposed',p_base);
 RETURN QUERY SELECT p_id,'proposed'::TEXT,p_base;
END $$;

CREATE FUNCTION li_api.decide_action_policy_change(p_id UUID,p_decision TEXT) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE p li_runtime_data.action_policy_proposals%ROWTYPE; v_current INTEGER; v_next INTEGER;
BEGIN
 SELECT * INTO p FROM li_runtime_data.action_policy_proposals WHERE id=p_id FOR UPDATE;
 IF NOT FOUND OR p.state<>'proposed' OR p_decision NOT IN ('approve','reject') THEN RAISE EXCEPTION 'Invalid policy decision'; END IF;
 SELECT version INTO v_current FROM li_runtime_data.action_policy_versions WHERE owner_user_id=p.owner_user_id AND superseded_at IS NULL FOR UPDATE;
 IF v_current<>p.base_version THEN UPDATE li_runtime_data.action_policy_proposals SET state='stale',resolved_at=NOW() WHERE id=p_id; RETURN jsonb_build_object('proposal_id',p_id,'state','stale'); END IF;
 IF p_decision='reject' THEN UPDATE li_runtime_data.action_policy_proposals SET state='rejected',resolved_at=NOW() WHERE id=p_id;
  INSERT INTO li_runtime_data.action_policy_events(owner_user_id,proposal_id,actor,event_type,from_version) VALUES(p.owner_user_id,p_id,'owner','rejected',v_current);
  RETURN jsonb_build_object('proposal_id',p_id,'state','rejected','effective_version',v_current); END IF;
 v_next:=v_current+1; UPDATE li_runtime_data.action_policy_versions SET superseded_at=NOW() WHERE owner_user_id=p.owner_user_id AND superseded_at IS NULL;
 INSERT INTO li_runtime_data.action_policy_versions(version,owner_user_id,policy,source,source_proposal_id) VALUES(v_next,p.owner_user_id,p.proposed_policy,'approved_proposal',p_id);
 UPDATE li_runtime_data.action_policy_proposals SET state='approved',resolved_at=NOW() WHERE id=p_id;
 INSERT INTO li_runtime_data.action_policy_events(owner_user_id,proposal_id,actor,event_type,from_version,to_version) VALUES(p.owner_user_id,p_id,'owner','approved',v_current,v_next);
 RETURN jsonb_build_object('proposal_id',p_id,'state','approved','effective_version',v_next);
END $$;

CREATE FUNCTION li_api.rollback_action_policy(p_target INTEGER,p_confirmation TEXT) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_current INTEGER; v_policy JSONB; v_next INTEGER;
BEGIN
 IF p_confirmation IS DISTINCT FROM 'confirm_action_policy_rollback' THEN RAISE EXCEPTION 'Owner confirmation required'; END IF;
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 SELECT version INTO v_current FROM li_runtime_data.action_policy_versions WHERE owner_user_id=v_user AND superseded_at IS NULL FOR UPDATE;
 SELECT policy INTO v_policy FROM li_runtime_data.action_policy_versions WHERE owner_user_id=v_user AND version=p_target;
 IF v_policy IS NULL OR p_target=v_current THEN RAISE EXCEPTION 'Invalid rollback target'; END IF;
 v_next:=v_current+1; v_policy:=jsonb_set(v_policy,'{policy_version}',to_jsonb(v_next));
 UPDATE li_runtime_data.action_policy_versions SET superseded_at=NOW() WHERE owner_user_id=v_user AND superseded_at IS NULL;
 INSERT INTO li_runtime_data.action_policy_versions(version,owner_user_id,policy,source) VALUES(v_next,v_user,v_policy,'rollback');
 INSERT INTO li_runtime_data.action_policy_events(owner_user_id,actor,event_type,from_version,to_version) VALUES(v_user,'owner','rollback',v_current,v_next);
 RETURN jsonb_build_object('state','rolled_back','restored_from_version',p_target,'effective_version',v_next);
END $$;

CREATE FUNCTION li_api.list_open_loops(p_limit INTEGER DEFAULT 100) RETURNS SETOF li_runtime_data.open_loops LANGUAGE sql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ SELECT o.* FROM li_runtime_data.open_loops o JOIN li_memory.users u ON u.id=o.owner_user_id WHERE u.user_key='christoffer' ORDER BY o.status,o.due_at NULLS LAST LIMIT LEAST(GREATEST(p_limit,1),500) $$;
CREATE FUNCTION li_api.create_open_loop(p_summary TEXT,p_owed TEXT,p_conversation UUID,p_request UUID,p_next TEXT,p_due TIMESTAMPTZ,p_urgency TEXT,p_approved BOOLEAN,p_sensitive BOOLEAN)
RETURNS SETOF li_runtime_data.open_loops LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_id UUID:=gen_random_uuid(); BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 IF p_sensitive AND NOT p_approved THEN RAISE EXCEPTION 'Sensitive commitment requires approval'; END IF;
 INSERT INTO li_runtime_data.open_loops(id,owner_user_id,commitment_summary,owed_to,source_conversation_id,source_request_id,next_action,due_at,urgency)
 VALUES(v_id,v_user,p_summary,p_owed,p_conversation,p_request,p_next,p_due,p_urgency);
 RETURN QUERY SELECT * FROM li_runtime_data.open_loops WHERE id=v_id; END $$;
CREATE FUNCTION li_api.transition_open_loop(p_id UUID,p_transition TEXT) RETURNS SETOF li_runtime_data.open_loops LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ BEGIN
 IF p_transition NOT IN ('postpone','raise','close') THEN RAISE EXCEPTION 'Invalid open-loop transition'; END IF;
 UPDATE li_runtime_data.open_loops SET status=CASE WHEN p_transition='postpone' THEN 'postponed' WHEN p_transition='close' THEN 'closed' ELSE 'open' END,
  postponement_count=postponement_count+CASE WHEN p_transition='postpone' THEN 1 ELSE 0 END,
  last_raised_at=CASE WHEN p_transition='raise' THEN NOW() ELSE last_raised_at END,closed_at=CASE WHEN p_transition='close' THEN NOW() ELSE NULL END WHERE id=p_id;
 RETURN QUERY SELECT * FROM li_runtime_data.open_loops WHERE id=p_id; END $$;

RESET ROLE;
REVOKE ALL ON FUNCTION li_api.get_action_policy_overview(),li_api.propose_action_policy_change(UUID,INTEGER,JSONB,TEXT),
 li_api.decide_action_policy_change(UUID,TEXT),li_api.rollback_action_policy(INTEGER,TEXT),li_api.list_open_loops(INTEGER),
 li_api.create_open_loop(TEXT,TEXT,UUID,UUID,TEXT,TIMESTAMPTZ,TEXT,BOOLEAN,BOOLEAN),li_api.transition_open_loop(UUID,TEXT)
 FROM PUBLIC,anon,authenticated,service_role,li_memory_theo,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.get_action_policy_overview(),li_api.propose_action_policy_change(UUID,INTEGER,JSONB,TEXT),
 li_api.list_open_loops(INTEGER),li_api.create_open_loop(TEXT,TEXT,UUID,UUID,TEXT,TIMESTAMPTZ,TEXT,BOOLEAN,BOOLEAN),
 li_api.transition_open_loop(UUID,TEXT) TO li_memory_api;
GRANT EXECUTE ON FUNCTION li_api.decide_action_policy_change(UUID,TEXT),li_api.rollback_action_policy(INTEGER,TEXT) TO li_memory_owner_confirmation;
REVOKE ALL PRIVILEGES ON li_runtime_data.action_policy_versions,li_runtime_data.action_policy_proposals,li_runtime_data.action_policy_events,
 li_runtime_data.rhythm_definitions,li_runtime_data.open_loops FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,
 li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
DO $$
DECLARE function_name TEXT;
BEGIN
 IF (SELECT added_create FROM migration_030_authority_state) THEN EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner'; END IF;
 IF (SELECT added_owner FROM migration_030_authority_state) THEN EXECUTE 'REVOKE li_memory_function_owner FROM postgres'; END IF;
 IF pg_catalog.has_function_privilege('li_memory_api','li_api.decide_action_policy_change(uuid,text)','EXECUTE')
 OR pg_catalog.has_function_privilege('li_memory_api','li_api.rollback_action_policy(integer,text)','EXECUTE') THEN
  RAISE EXCEPTION 'Action policy privilege escalation boundary is broader than intended'; END IF;
 FOREACH function_name IN ARRAY ARRAY[
  'li_api.get_action_policy_overview()','li_api.propose_action_policy_change(uuid,integer,jsonb,text)',
  'li_api.decide_action_policy_change(uuid,text)','li_api.rollback_action_policy(integer,text)',
  'li_api.list_open_loops(integer)','li_api.create_open_loop(text,text,uuid,uuid,text,timestamptz,text,boolean,boolean)',
  'li_api.transition_open_loop(uuid,text)'
 ] LOOP
  IF (SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
      WHERE p.oid=function_name::REGPROCEDURE) IS DISTINCT FROM 'li_memory_function_owner' THEN
   RAISE EXCEPTION 'Function % has unexpected owner',function_name;
  END IF;
 END LOOP;
 IF (SELECT added_create FROM migration_030_authority_state)
    AND pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN
  RAISE EXCEPTION 'Temporary li_api CREATE authority was not removed'; END IF;
 IF (SELECT added_owner FROM migration_030_authority_state)
    AND (pg_catalog.pg_has_role('postgres','li_memory_function_owner','SET')
      OR pg_catalog.pg_has_role('postgres','li_memory_function_owner','USAGE')) THEN
  RAISE EXCEPTION 'Temporary function-owner authority was not removed'; END IF;
END $$;

INSERT INTO li_memory.schema_versions(version,description) VALUES('0.30','Governed action policy, rhythms, and open loops');
COMMIT;
