BEGIN;

ALTER TABLE li_runtime_data.specialist_interactions
  ADD COLUMN explicit_request BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN used_in_final BOOLEAN,
  ADD COLUMN action_taken BOOLEAN,
  ADD COLUMN topic_keys TEXT[] NOT NULL DEFAULT '{}';
UPDATE li_runtime_data.specialist_interactions
SET explicit_request = request_text ~* ('(^|[^a-z])' || specialist_key || '([^a-z]|$)');

CREATE TABLE li_runtime_data.agent_registry_state (
  owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
  agent_key TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'idle' CHECK (state IN ('idle','paused','archived')),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY(owner_user_id, agent_key)
);
CREATE TABLE li_runtime_data.agent_analytics_settings (
  owner_user_id UUID PRIMARY KEY REFERENCES li_memory.users(id),
  relevance_cadence_months INTEGER CHECK (relevance_cadence_months IN (1,2,3,6)),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE li_runtime_data.agent_recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
  subject_agent TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('create','keep','pause','merge','archive','remove')),
  rationale TEXT NOT NULL, evidence JSONB NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'pending_approval'
    CHECK(status IN ('pending_approval','approved_pending_execution','rejected','executed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), reviewed_at TIMESTAMPTZ
);
ALTER TABLE li_runtime_data.agent_registry_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.agent_analytics_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.agent_recommendations ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_state_function_access ON li_runtime_data.agent_registry_state FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY agent_settings_function_access ON li_runtime_data.agent_analytics_settings FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY agent_recommendations_function_access ON li_runtime_data.agent_recommendations FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT,UPDATE ON li_runtime_data.agent_registry_state,li_runtime_data.agent_analytics_settings,li_runtime_data.agent_recommendations TO li_memory_function_owner;

GRANT li_memory_function_owner TO postgres;
GRANT USAGE,CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.list_agent_analytics_events()
RETURNS TABLE(interaction_id UUID,request_id UUID,specialist_key TEXT,status TEXT,request_text TEXT,outcome JSONB,
 started_at TIMESTAMPTZ,completed_at TIMESTAMPTZ,explicit_request BOOLEAN,used_in_final BOOLEAN,action_taken BOOLEAN,topic_keys TEXT[])
LANGUAGE sql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
 SELECT i.id,i.request_id,i.specialist_key,i.status,i.request_text,i.outcome,i.started_at,i.completed_at,
 i.explicit_request,i.used_in_final,i.action_taken,i.topic_keys FROM li_runtime_data.specialist_interactions i
 JOIN li_memory.users u ON u.id=i.owner_user_id WHERE u.user_key='christoffer' AND u.status='active' ORDER BY i.started_at DESC;
$$;

CREATE OR REPLACE FUNCTION li_api.start_specialist_interaction(p_conversation UUID,p_request UUID,
 p_specialist TEXT,p_request_text TEXT)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_conversation,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_id UUID;
BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 IF p_conversation IS NOT NULL AND NOT EXISTS(SELECT 1 FROM li_conversation.conversations WHERE id=p_conversation AND owner_user_id=v_user)
 THEN RAISE EXCEPTION 'Conversation not found'; END IF;
 INSERT INTO li_runtime_data.specialist_interactions(owner_user_id,conversation_id,request_id,specialist_key,status,request_text,explicit_request)
 VALUES(v_user,p_conversation,p_request,p_specialist,'active',p_request_text,
        p_request_text ~* ('(^|[^a-z])' || p_specialist || '([^a-z]|$)')) RETURNING id INTO v_id;
 RETURN v_id; END; $$;

CREATE FUNCTION li_api.get_agent_analytics_settings()
RETURNS TABLE(relevance_cadence_months INTEGER,updated_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 INSERT INTO li_runtime_data.agent_analytics_settings(owner_user_id,relevance_cadence_months) VALUES(v_user,1) ON CONFLICT DO NOTHING;
 RETURN QUERY SELECT s.relevance_cadence_months,s.updated_at FROM li_runtime_data.agent_analytics_settings s WHERE s.owner_user_id=v_user; END; $$;

CREATE FUNCTION li_api.list_agent_states()
RETURNS TABLE(agent_key TEXT,state TEXT,updated_at TIMESTAMPTZ)
LANGUAGE sql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
 SELECT s.agent_key,s.state,s.updated_at FROM li_runtime_data.agent_registry_state s JOIN li_memory.users u ON u.id=s.owner_user_id
 WHERE u.user_key='christoffer' AND u.status='active'; $$;

CREATE FUNCTION li_api.set_agent_relevance_cadence(p_months INTEGER)
RETURNS TABLE(relevance_cadence_months INTEGER,updated_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; BEGIN IF p_months IS NOT NULL AND p_months NOT IN (1,2,3,6) THEN RAISE EXCEPTION 'Unsupported cadence'; END IF;
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 INSERT INTO li_runtime_data.agent_analytics_settings(owner_user_id,relevance_cadence_months) VALUES(v_user,p_months)
 ON CONFLICT(owner_user_id) DO UPDATE SET relevance_cadence_months=p_months,updated_at=NOW();
 RETURN QUERY SELECT s.relevance_cadence_months,s.updated_at FROM li_runtime_data.agent_analytics_settings s WHERE s.owner_user_id=v_user; END; $$;

CREATE FUNCTION li_api.replace_agent_recommendations(p_items JSONB)
RETURNS TABLE(recommendation_id UUID,subject_agent TEXT,action TEXT,rationale TEXT,status TEXT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 INSERT INTO li_runtime_data.agent_recommendations(owner_user_id,subject_agent,action,rationale,evidence)
 SELECT v_user,x->>'subject_agent',x->>'action',x->>'rationale',x FROM jsonb_array_elements(p_items) x;
 RETURN QUERY SELECT r.id,r.subject_agent,r.action,r.rationale,r.status FROM li_runtime_data.agent_recommendations r
 WHERE r.owner_user_id=v_user AND r.status='pending_approval' ORDER BY r.created_at DESC; END; $$;

CREATE FUNCTION li_api.review_agent_recommendation(p_id UUID,p_decision TEXT)
RETURNS TABLE(recommendation_id UUID,subject_agent TEXT,action TEXT,status TEXT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; BEGIN IF p_decision NOT IN ('approve','reject') THEN RAISE EXCEPTION 'Invalid decision'; END IF;
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 UPDATE li_runtime_data.agent_recommendations r SET status=CASE WHEN p_decision='approve' THEN 'approved_pending_execution' ELSE 'rejected' END,reviewed_at=NOW()
 WHERE r.id=p_id AND r.owner_user_id=v_user AND r.status='pending_approval';
 RETURN QUERY SELECT r.id,r.subject_agent,r.action,r.status FROM li_runtime_data.agent_recommendations r WHERE r.id=p_id AND r.owner_user_id=v_user; END; $$;

RESET ROLE;
REVOKE ALL ON FUNCTION li_api.list_agent_analytics_events(),li_api.get_agent_analytics_settings(),li_api.list_agent_states(),li_api.set_agent_relevance_cadence(INTEGER),li_api.replace_agent_recommendations(JSONB),li_api.review_agent_recommendation(UUID,TEXT) FROM PUBLIC,anon,authenticated,service_role,li_memory_theo,li_memory_owner_confirmation;
GRANT EXECUTE ON FUNCTION li_api.list_agent_analytics_events(),li_api.get_agent_analytics_settings(),li_api.list_agent_states(),li_api.set_agent_relevance_cadence(INTEGER),li_api.replace_agent_recommendations(JSONB),li_api.review_agent_recommendation(UUID,TEXT) TO li_memory_api;
REVOKE ALL PRIVILEGES ON li_runtime_data.agent_registry_state,li_runtime_data.agent_analytics_settings,li_runtime_data.agent_recommendations FROM li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation;
REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;
INSERT INTO li_memory.schema_versions(version,description) VALUES('0.18','Agent analytics, relevance cadence, lifecycle state, and approval queue') ON CONFLICT(version) DO NOTHING;
COMMIT;
