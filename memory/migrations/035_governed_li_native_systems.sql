BEGIN;

DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.34') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 035 requires applied schema 0.34';
 END IF;
 IF EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.35') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Schema version 0.35 is already claimed';
 END IF;
END $$;

CREATE TABLE li_runtime_data.skills(
 skill_id TEXT NOT NULL CHECK(skill_id ~ '^[a-z0-9][a-z0-9-]{2,63}$'),
 version INTEGER NOT NULL CHECK(version>0), name TEXT NOT NULL, domain TEXT NOT NULL,
 description TEXT NOT NULL, owner_scope TEXT NOT NULL CHECK(owner_scope IN('li','owner','community')),
 trust_state TEXT NOT NULL CHECK(trust_state IN('draft','untrusted','trial','trusted','retired')),
 created_from TEXT NOT NULL, dependencies JSONB NOT NULL DEFAULT '[]',
 required_tools JSONB NOT NULL DEFAULT '[]', required_providers JSONB NOT NULL DEFAULT '[]',
 specialist_compatibility JSONB NOT NULL DEFAULT '[]', sensitivity TEXT NOT NULL,
 validation_tests JSONB NOT NULL DEFAULT '[]', review_status TEXT NOT NULL,
 body_markdown TEXT NOT NULL, references_manifest JSONB NOT NULL DEFAULT '[]',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), retired_at TIMESTAMPTZ,
 PRIMARY KEY(skill_id,version),
 CHECK(owner_scope<>'community' OR trust_state IN('untrusted','retired')),
 CHECK(trust_state<>'trusted' OR (review_status='approved' AND jsonb_array_length(validation_tests)>0))
);
CREATE TABLE li_runtime_data.skill_outcomes(
 outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), skill_id TEXT NOT NULL, version INTEGER NOT NULL,
 used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), task_succeeded BOOLEAN, user_corrected BOOLEAN,
 action_followed BOOLEAN, evidence TEXT, FOREIGN KEY(skill_id,version)
 REFERENCES li_runtime_data.skills(skill_id,version)
);
CREATE TABLE li_runtime_data.context_selections(
 selection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id UUID,
 request_id UUID NOT NULL, caller TEXT NOT NULL, selected_classes JSONB NOT NULL,
 omitted_classes JSONB NOT NULL, selection_reasons JSONB NOT NULL,
 estimated_tokens INTEGER NOT NULL CHECK(estimated_tokens>=0), budget INTEGER NOT NULL CHECK(budget>0),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX conversation_messages_fts_idx ON li_conversation.messages
 USING GIN(to_tsvector('simple',content));
CREATE TABLE li_runtime_data.conversation_compressions(
 compression_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id UUID NOT NULL
 REFERENCES li_conversation.conversations(id) ON DELETE CASCADE,
 version INTEGER NOT NULL CHECK(version>0), summary TEXT NOT NULL, source_message_ids JSONB NOT NULL,
 unresolved_commitments JSONB NOT NULL DEFAULT '[]', action_records JSONB NOT NULL DEFAULT '[]',
 quality_checks JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(conversation_id,version)
);
CREATE TABLE li_runtime_data.watcher_events(
 event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), watcher_key TEXT NOT NULL,
 occurrence_key TEXT NOT NULL UNIQUE, condition_name TEXT NOT NULL, payload JSONB NOT NULL,
 wake_li BOOLEAN NOT NULL, llm_calls_avoided INTEGER NOT NULL DEFAULT 1 CHECK(llm_calls_avoided=1),
 observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), delivered_at TIMESTAMPTZ
);
CREATE TABLE li_runtime_data.temporary_worker_runs(
 run_id UUID PRIMARY KEY, role TEXT NOT NULL, task_fingerprint CHAR(64) NOT NULL,
 status TEXT NOT NULL CHECK(status IN('created','running','succeeded','failed','timed_out','cancelled')),
 model_key TEXT, allowed_tools JSONB NOT NULL DEFAULT '[]', max_seconds INTEGER NOT NULL,
 max_cost_usd NUMERIC(8,4) NOT NULL, result_metadata JSONB NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ
);
CREATE TABLE li_runtime_data.model_registry(
 model_key TEXT PRIMARY KEY, provider TEXT NOT NULL, model_name TEXT NOT NULL,
 capabilities JSONB NOT NULL, cost_metadata JSONB NOT NULL, context_limit INTEGER NOT NULL,
 health TEXT NOT NULL CHECK(health IN('healthy','degraded','unavailable','not_configured')),
 privacy_constraints JSONB NOT NULL, is_primary BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX one_primary_model_idx ON li_runtime_data.model_registry(is_primary) WHERE is_primary;
CREATE TABLE li_runtime_data.tool_registry(
 tool_key TEXT PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN('read','write')),
 action_class INTEGER NOT NULL CHECK(action_class BETWEEN 0 AND 3), approval_required BOOLEAN NOT NULL,
 sensitivity TEXT NOT NULL, provider TEXT NOT NULL, availability TEXT NOT NULL,
 cost_metadata JSONB NOT NULL, rate_limits JSONB NOT NULL, allowed_callers JSONB NOT NULL,
 evidence_required BOOLEAN NOT NULL, health JSONB NOT NULL,
 CHECK(action_class<3 OR approval_required), CHECK(mode<>'write' OR allowed_callers ? 'li')
);
CREATE TABLE li_runtime_data.delivery_adapters(
 adapter_key TEXT PRIMARY KEY CHECK(adapter_key IN('web','native','push','email','sms')),
 status TEXT NOT NULL CHECK(status IN('available','ready','not_configured')),
 can_carry_approvals BOOLEAN NOT NULL, grants_authority BOOLEAN NOT NULL DEFAULT FALSE,
 CHECK(NOT grants_authority)
);
CREATE TABLE li_runtime_data.heavy_work_audit(
 task_id UUID PRIMARY KEY, status TEXT NOT NULL, enabled BOOLEAN NOT NULL DEFAULT FALSE,
 allowed_tools JSONB NOT NULL DEFAULT '[]', network_allowlist JSONB NOT NULL DEFAULT '[]',
 credential_reference_count INTEGER NOT NULL DEFAULT 0, max_seconds INTEGER NOT NULL,
 max_cost_usd NUMERIC(8,4) NOT NULL, result_metadata JSONB NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ,
 CHECK(NOT enabled)
);

ALTER TABLE li_runtime_data.skills,li_runtime_data.skill_outcomes,
 li_runtime_data.context_selections,li_runtime_data.conversation_compressions,
 li_runtime_data.watcher_events,li_runtime_data.temporary_worker_runs,
 li_runtime_data.model_registry,li_runtime_data.tool_registry,
 li_runtime_data.delivery_adapters,li_runtime_data.heavy_work_audit ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION li_api.search_conversation_history(p_query TEXT,p_limit INTEGER DEFAULT 10)
RETURNS TABLE(conversation_id UUID,message_id UUID,role TEXT,snippet TEXT,created_at TIMESTAMPTZ,rank REAL)
LANGUAGE sql SECURITY DEFINER SET search_path=li_conversation,li_memory,pg_catalog,pg_temp AS $$
 SELECT m.conversation_id,m.id AS message_id,m.role,
  ts_headline('simple',m.content,plainto_tsquery('simple',p_query),'MaxFragments=2,MaxWords=45') AS snippet,
  m.created_at,ts_rank_cd(to_tsvector('simple',m.content),plainto_tsquery('simple',p_query)) AS rank
 FROM li_conversation.messages m JOIN li_conversation.conversations c
  ON c.id=m.conversation_id JOIN li_memory.users u ON u.id=c.owner_user_id
 WHERE u.user_key='christoffer' AND u.status='active' AND length(trim(p_query))>0
  AND to_tsvector('simple',m.content) @@ plainto_tsquery('simple',p_query)
 ORDER BY rank DESC,m.created_at DESC LIMIT LEAST(GREATEST(p_limit,1),25)
$$;
CREATE FUNCTION li_api.list_skills_overview()
RETURNS TABLE(skill_id TEXT,version INTEGER,name TEXT,domain TEXT,description TEXT,
 owner_scope TEXT,trust_state TEXT,sensitivity TEXT,review_status TEXT,last_used TIMESTAMPTZ,
 success_count BIGINT,failure_count BIGINT)
LANGUAGE sql SECURITY DEFINER SET search_path=li_runtime_data,pg_catalog,pg_temp AS $$
 SELECT s.skill_id,s.version,s.name,s.domain,s.description,s.owner_scope,s.trust_state,
  s.sensitivity,s.review_status,max(o.used_at),
  count(*) FILTER(WHERE o.task_succeeded IS TRUE),
  count(*) FILTER(WHERE o.task_succeeded IS FALSE)
 FROM li_runtime_data.skills s LEFT JOIN li_runtime_data.skill_outcomes o
  ON o.skill_id=s.skill_id AND o.version=s.version
 GROUP BY s.skill_id,s.version,s.name,s.domain,s.description,s.owner_scope,s.trust_state,
  s.sensitivity,s.review_status ORDER BY s.name,s.version DESC
$$;
GRANT SELECT ON li_runtime_data.skills,li_runtime_data.skill_outcomes
 TO li_memory_function_owner;
ALTER FUNCTION li_api.search_conversation_history(TEXT,INTEGER)
 OWNER TO li_memory_function_owner;
ALTER FUNCTION li_api.list_skills_overview()
 OWNER TO li_memory_function_owner;
REVOKE ALL ON FUNCTION li_api.search_conversation_history(TEXT,INTEGER) FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION li_api.search_conversation_history(TEXT,INTEGER) TO li_backend_runtime;
REVOKE ALL ON FUNCTION li_api.list_skills_overview() FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION li_api.list_skills_overview() TO li_backend_runtime;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA li_runtime_data FROM PUBLIC,anon,authenticated,service_role;

INSERT INTO li_runtime_data.model_registry(model_key,provider,model_name,capabilities,cost_metadata,
 context_limit,health,privacy_constraints,is_primary)
VALUES('claude-primary','anthropic','configured-at-runtime','["reasoning","structured_output","coding"]',
 '{}',200000,'not_configured','{"private_data":true}',TRUE);
INSERT INTO li_runtime_data.delivery_adapters(adapter_key,status,can_carry_approvals) VALUES
 ('web','available',TRUE),('native','ready',TRUE),('push','not_configured',FALSE),
 ('email','not_configured',FALSE),('sms','not_configured',FALSE);

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.35','Governed skills, context selection, historical search, compression, watchers, bounded workers, model/tool/delivery registries, and disabled heavy-work audit');
COMMIT;
