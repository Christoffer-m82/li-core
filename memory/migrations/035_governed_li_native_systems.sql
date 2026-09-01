BEGIN;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.34') THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 035 requires applied schema 0.34'; END IF;
 IF EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.35') THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Schema version 0.35 is already claimed'; END IF;
 IF (SELECT count(*) FROM li_memory.users WHERE user_key='christoffer' AND status='active')<>1 THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 035 requires exactly one active owner'; END IF;
END $$;

CREATE TABLE li_runtime_data.skills(
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), skill_id TEXT NOT NULL CHECK(skill_id ~ '^[a-z0-9][a-z0-9-]{2,63}$'),
 version INTEGER NOT NULL CHECK(version>0), name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 100), domain TEXT NOT NULL CHECK(length(domain) BETWEEN 1 AND 80),
 description TEXT NOT NULL CHECK(length(description) BETWEEN 1 AND 500), owner_scope TEXT NOT NULL CHECK(owner_scope IN('li','owner','community')),
 trust_state TEXT NOT NULL CHECK(trust_state IN('draft','untrusted','trial','trusted','retired')), created_from TEXT NOT NULL CHECK(length(created_from) BETWEEN 1 AND 300),
 dependencies JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(dependencies)='array' AND pg_column_size(dependencies)<=16384),
 required_tools JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(required_tools)='array' AND pg_column_size(required_tools)<=16384),
 required_providers JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(required_providers)='array' AND pg_column_size(required_providers)<=16384),
 specialist_compatibility JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(specialist_compatibility)='array' AND pg_column_size(specialist_compatibility)<=16384),
 sensitivity TEXT NOT NULL CHECK(sensitivity IN('standard','personal','restricted')),
 validation_tests JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(validation_tests)='array' AND pg_column_size(validation_tests)<=32768),
 review_status TEXT NOT NULL CHECK(review_status IN('pending','approved','rejected')), body_markdown TEXT NOT NULL CHECK(length(body_markdown) BETWEEN 1 AND 200000),
 references_manifest JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(references_manifest)='array' AND pg_column_size(references_manifest)<=32768),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), retired_at TIMESTAMPTZ, PRIMARY KEY(owner_user_id,skill_id,version),
 CHECK(owner_scope<>'community' OR trust_state IN('untrusted','retired')), CHECK(trust_state<>'trusted' OR (review_status='approved' AND jsonb_array_length(validation_tests)>0)));
CREATE TABLE li_runtime_data.skill_outcomes(
 outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), skill_id TEXT NOT NULL, version INTEGER NOT NULL,
 used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), task_succeeded BOOLEAN, user_corrected BOOLEAN, action_followed BOOLEAN, evidence TEXT CHECK(evidence IS NULL OR length(evidence)<=500),
 FOREIGN KEY(owner_user_id,skill_id,version) REFERENCES li_runtime_data.skills(owner_user_id,skill_id,version));
CREATE TABLE li_runtime_data.context_selections(
 selection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), conversation_id UUID REFERENCES li_conversation.conversations(id) ON DELETE CASCADE,
 request_id UUID NOT NULL, caller TEXT NOT NULL CHECK(caller IN('li','specialist','temporary','heavy')),
 selected_classes JSONB NOT NULL CHECK(jsonb_typeof(selected_classes)='array' AND pg_column_size(selected_classes)<=16384),
 omitted_classes JSONB NOT NULL CHECK(jsonb_typeof(omitted_classes)='array' AND pg_column_size(omitted_classes)<=16384),
 selection_reasons JSONB NOT NULL CHECK(jsonb_typeof(selection_reasons)='array' AND pg_column_size(selection_reasons)<=32768),
 estimated_tokens INTEGER NOT NULL CHECK(estimated_tokens>=0), budget INTEGER NOT NULL CHECK(budget BETWEEN 1 AND 1000000), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX conversation_messages_fts_idx ON li_conversation.messages USING GIN(to_tsvector('simple'::regconfig,content));
CREATE UNIQUE INDEX conversations_owner_id_idx ON li_conversation.conversations(owner_user_id,id);
CREATE TABLE li_runtime_data.conversation_compressions(
 compression_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), conversation_id UUID NOT NULL,
 version INTEGER NOT NULL CHECK(version>0), summary TEXT NOT NULL CHECK(length(summary) BETWEEN 1 AND 50000),
 source_message_ids JSONB NOT NULL CHECK(jsonb_typeof(source_message_ids)='array' AND pg_column_size(source_message_ids)<=65536),
 unresolved_commitments JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(unresolved_commitments)='array' AND pg_column_size(unresolved_commitments)<=65536),
 action_records JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(action_records)='array' AND pg_column_size(action_records)<=65536),
 quality_checks JSONB NOT NULL CHECK(jsonb_typeof(quality_checks)='object' AND pg_column_size(quality_checks)<=8192), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(owner_user_id,conversation_id,version), FOREIGN KEY(owner_user_id,conversation_id) REFERENCES li_conversation.conversations(owner_user_id,id) ON DELETE CASCADE);
CREATE TABLE li_runtime_data.watcher_events(
 event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), watcher_key TEXT NOT NULL CHECK(length(watcher_key) BETWEEN 3 AND 64),
 occurrence_key TEXT NOT NULL CHECK(length(occurrence_key) BETWEEN 1 AND 500), condition_name TEXT NOT NULL CHECK(length(condition_name) BETWEEN 1 AND 80),
 payload JSONB NOT NULL CHECK(jsonb_typeof(payload)='object' AND pg_column_size(payload)<=32768), wake_li BOOLEAN NOT NULL,
 llm_calls_avoided INTEGER NOT NULL DEFAULT 1 CHECK(llm_calls_avoided=1), observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), delivered_at TIMESTAMPTZ, UNIQUE(owner_user_id,occurrence_key));
CREATE TABLE li_runtime_data.temporary_worker_runs(
 run_id UUID PRIMARY KEY, owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), role TEXT NOT NULL CHECK(length(role) BETWEEN 1 AND 120),
 task_fingerprint CHAR(64) NOT NULL CHECK(task_fingerprint ~ '^[a-f0-9]{64}$'), status TEXT NOT NULL CHECK(status IN('created','running','succeeded','failed','timed_out','cancelled')),
 model_key TEXT, allowed_tools JSONB NOT NULL DEFAULT '[]' CHECK(allowed_tools='[]'::jsonb), max_seconds INTEGER NOT NULL CHECK(max_seconds BETWEEN 1 AND 300),
 max_cost_usd NUMERIC(8,4) NOT NULL CHECK(max_cost_usd BETWEEN 0 AND 5), result_metadata JSONB NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(result_metadata)='object' AND pg_column_size(result_metadata)<=32768),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ);
CREATE TABLE li_runtime_data.model_registry(
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), model_key TEXT NOT NULL, provider TEXT NOT NULL CHECK(length(provider) BETWEEN 1 AND 80), model_name TEXT NOT NULL CHECK(length(model_name) BETWEEN 1 AND 160),
 capabilities JSONB NOT NULL CHECK(jsonb_typeof(capabilities)='array' AND pg_column_size(capabilities)<=16384), cost_metadata JSONB NOT NULL CHECK(jsonb_typeof(cost_metadata)='object' AND pg_column_size(cost_metadata)<=8192),
 context_limit INTEGER NOT NULL CHECK(context_limit>0), health TEXT NOT NULL CHECK(health IN('healthy','degraded','unavailable','not_configured')),
 privacy_constraints JSONB NOT NULL CHECK(jsonb_typeof(privacy_constraints)='object' AND pg_column_size(privacy_constraints)<=8192), is_primary BOOLEAN NOT NULL DEFAULT FALSE, PRIMARY KEY(owner_user_id,model_key));
CREATE UNIQUE INDEX one_primary_model_idx ON li_runtime_data.model_registry(owner_user_id) WHERE is_primary;
CREATE TABLE li_runtime_data.tool_registry(
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), tool_key TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode IN('read','write')), action_class INTEGER NOT NULL CHECK(action_class BETWEEN 0 AND 3),
 approval_required BOOLEAN NOT NULL, sensitivity TEXT NOT NULL CHECK(sensitivity IN('standard','personal','restricted')), provider TEXT NOT NULL,
 availability TEXT NOT NULL CHECK(availability IN('available','degraded','not_configured')), cost_metadata JSONB NOT NULL CHECK(jsonb_typeof(cost_metadata)='object' AND pg_column_size(cost_metadata)<=8192),
 rate_limits JSONB NOT NULL CHECK(jsonb_typeof(rate_limits)='object' AND pg_column_size(rate_limits)<=8192), allowed_callers JSONB NOT NULL CHECK(jsonb_typeof(allowed_callers)='array' AND pg_column_size(allowed_callers)<=8192),
 evidence_required BOOLEAN NOT NULL, health JSONB NOT NULL CHECK(jsonb_typeof(health)='object' AND pg_column_size(health)<=8192), PRIMARY KEY(owner_user_id,tool_key),
 CHECK(action_class<3 OR approval_required), CHECK(mode<>'write' OR allowed_callers @> '["li"]'::jsonb));
CREATE TABLE li_runtime_data.delivery_adapters(
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), adapter_key TEXT NOT NULL CHECK(adapter_key IN('web','native','push','email','sms')),
 status TEXT NOT NULL CHECK(status IN('available','ready','not_configured')), can_carry_approvals BOOLEAN NOT NULL, grants_authority BOOLEAN NOT NULL DEFAULT FALSE CHECK(NOT grants_authority), PRIMARY KEY(owner_user_id,adapter_key));
CREATE TABLE li_runtime_data.heavy_work_audit(
 task_id UUID PRIMARY KEY, owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), status TEXT NOT NULL CHECK(status IN('rejected_disabled','rejected_policy','succeeded','failed','timed_out','cancelled')),
 enabled BOOLEAN NOT NULL DEFAULT FALSE CHECK(NOT enabled), allowed_tools JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(allowed_tools)='array' AND pg_column_size(allowed_tools)<=8192),
 network_allowlist JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(network_allowlist)='array' AND pg_column_size(network_allowlist)<=8192), credential_reference_count INTEGER NOT NULL DEFAULT 0 CHECK(credential_reference_count=0),
 max_seconds INTEGER NOT NULL CHECK(max_seconds BETWEEN 1 AND 1800), max_cost_usd NUMERIC(8,4) NOT NULL CHECK(max_cost_usd BETWEEN 0 AND 10),
 result_metadata JSONB NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(result_metadata)='object' AND pg_column_size(result_metadata)<=32768), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ);

ALTER TABLE li_runtime_data.skills,li_runtime_data.skill_outcomes,li_runtime_data.context_selections,li_runtime_data.conversation_compressions,
 li_runtime_data.watcher_events,li_runtime_data.temporary_worker_runs,li_runtime_data.model_registry,li_runtime_data.tool_registry,
 li_runtime_data.delivery_adapters,li_runtime_data.heavy_work_audit ENABLE ROW LEVEL SECURITY;
CREATE POLICY skills_function_access ON li_runtime_data.skills FOR SELECT TO li_memory_function_owner USING(TRUE);
CREATE POLICY skill_outcomes_function_access ON li_runtime_data.skill_outcomes FOR SELECT TO li_memory_function_owner USING(TRUE);
GRANT SELECT ON li_runtime_data.skills,li_runtime_data.skill_outcomes TO li_memory_function_owner;

CREATE TEMP TABLE migration_035_authority_state(migration_role NAME,added_owner BOOLEAN,added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_035_authority_state SELECT CURRENT_USER,NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_035_authority_state) THEN EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I',(SELECT migration_role FROM migration_035_authority_state)); END IF;
 IF (SELECT added_create FROM migration_035_authority_state) THEN EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner'; END IF;
END $$;
DO $$ BEGIN
 IF NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET') THEN RAISE EXCEPTION 'Migration role cannot assume li_memory_function_owner'; END IF;
 IF NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN RAISE EXCEPTION 'Function owner cannot create in li_api'; END IF;
END $$;
SET LOCAL ROLE li_memory_function_owner;
CREATE FUNCTION li_api.search_conversation_history(p_query TEXT,p_limit INTEGER DEFAULT 10)
RETURNS TABLE(conversation_id UUID,message_id UUID,role TEXT,snippet TEXT,created_at TIMESTAMPTZ,rank REAL)
LANGUAGE sql SECURITY DEFINER SET search_path=li_conversation,li_memory,pg_catalog,pg_temp AS $$
 WITH q AS (SELECT plainto_tsquery('simple'::regconfig,left(btrim(COALESCE(p_query,'')),300)) query)
 SELECT m.conversation_id,m.id,m.role,left(ts_headline('simple'::regconfig,m.content,q.query,'MaxFragments=2,MaxWords=45'),1200),
  m.created_at,ts_rank_cd(to_tsvector('simple'::regconfig,m.content),q.query)
 FROM q,li_conversation.messages m JOIN li_conversation.conversations c ON c.id=m.conversation_id JOIN li_memory.users u ON u.id=c.owner_user_id
 WHERE u.user_key='christoffer' AND u.status='active' AND length(btrim(COALESCE(p_query,''))) BETWEEN 2 AND 300
  AND to_tsvector('simple'::regconfig,m.content) @@ q.query ORDER BY 6 DESC,m.created_at DESC LIMIT LEAST(GREATEST(COALESCE(p_limit,10),1),25)
$$;
CREATE FUNCTION li_api.list_skills_overview()
RETURNS TABLE(skill_id TEXT,version INTEGER,name TEXT,domain TEXT,description TEXT,owner_scope TEXT,trust_state TEXT,sensitivity TEXT,review_status TEXT,last_used TIMESTAMPTZ,success_count BIGINT,failure_count BIGINT)
LANGUAGE sql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
 SELECT s.skill_id,s.version,s.name,s.domain,s.description,s.owner_scope,s.trust_state,s.sensitivity,s.review_status,max(o.used_at),
  count(*) FILTER(WHERE o.task_succeeded IS TRUE),count(*) FILTER(WHERE o.task_succeeded IS FALSE)
 FROM li_runtime_data.skills s JOIN li_memory.users u ON u.id=s.owner_user_id LEFT JOIN li_runtime_data.skill_outcomes o
  ON o.owner_user_id=s.owner_user_id AND o.skill_id=s.skill_id AND o.version=s.version
 WHERE u.user_key='christoffer' AND u.status='active'
 GROUP BY s.owner_user_id,s.skill_id,s.version,s.name,s.domain,s.description,s.owner_scope,s.trust_state,s.sensitivity,s.review_status ORDER BY s.name,s.version DESC
$$;
RESET ROLE;
REVOKE ALL ON FUNCTION li_api.search_conversation_history(TEXT,INTEGER),li_api.list_skills_overview()
 FROM PUBLIC,anon,authenticated,service_role,li_memory_api,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.search_conversation_history(TEXT,INTEGER),li_api.list_skills_overview() TO li_memory_api;
REVOKE ALL PRIVILEGES ON li_runtime_data.skills,li_runtime_data.skill_outcomes,li_runtime_data.context_selections,li_runtime_data.conversation_compressions,
 li_runtime_data.watcher_events,li_runtime_data.temporary_worker_runs,li_runtime_data.model_registry,li_runtime_data.tool_registry,
 li_runtime_data.delivery_adapters,li_runtime_data.heavy_work_audit
 FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;

INSERT INTO li_runtime_data.model_registry(owner_user_id,model_key,provider,model_name,capabilities,cost_metadata,context_limit,health,privacy_constraints,is_primary)
SELECT id,'claude-primary','anthropic','configured-at-runtime','["reasoning","structured_output","coding"]','{}',200000,'not_configured','{"private_data":true}',TRUE
FROM li_memory.users WHERE user_key='christoffer' AND status='active';
INSERT INTO li_runtime_data.delivery_adapters(owner_user_id,adapter_key,status,can_carry_approvals)
SELECT u.id,v.adapter_key,v.status,v.can_carry_approvals FROM li_memory.users u CROSS JOIN (VALUES
 ('web','available',TRUE),('native','ready',TRUE),('push','not_configured',FALSE),('email','not_configured',FALSE),('sms','not_configured',FALSE)) v(adapter_key,status,can_carry_approvals)
WHERE u.user_key='christoffer' AND u.status='active';

DO $$ DECLARE function_name TEXT; BEGIN
 IF (SELECT added_create FROM migration_035_authority_state) THEN REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner; END IF;
 IF (SELECT added_owner FROM migration_035_authority_state) THEN EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I',(SELECT migration_role FROM migration_035_authority_state)); END IF;
 FOREACH function_name IN ARRAY ARRAY['li_api.search_conversation_history(text,integer)','li_api.list_skills_overview()'] LOOP
  IF (SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner WHERE p.oid=function_name::REGPROCEDURE) IS DISTINCT FROM 'li_memory_function_owner' THEN RAISE EXCEPTION 'Function % has unexpected owner',function_name; END IF;
 END LOOP;
 IF NOT pg_catalog.has_function_privilege('li_backend_runtime','li_api.search_conversation_history(text,integer)','EXECUTE') OR NOT pg_catalog.has_function_privilege('li_backend_runtime','li_api.list_skills_overview()','EXECUTE') THEN RAISE EXCEPTION 'Backend runtime lost governed-system function execution'; END IF;
 IF pg_catalog.has_table_privilege('li_backend_runtime','li_runtime_data.skills','SELECT') OR pg_catalog.has_table_privilege('li_retention_runtime','li_runtime_data.heavy_work_audit','SELECT') THEN RAISE EXCEPTION 'Governed-system direct table boundary is broader than intended'; END IF;
 IF (SELECT added_create FROM migration_035_authority_state) AND pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN RAISE EXCEPTION 'Temporary li_api CREATE authority was not removed'; END IF;
 IF (SELECT added_owner FROM migration_035_authority_state) AND (pg_catalog.pg_has_role((SELECT migration_role FROM migration_035_authority_state),'li_memory_function_owner','SET') OR pg_catalog.pg_has_role((SELECT migration_role FROM migration_035_authority_state),'li_memory_function_owner','USAGE')) THEN RAISE EXCEPTION 'Temporary function-owner authority was not removed'; END IF;
END $$;
INSERT INTO li_memory.schema_versions(version,description) VALUES('0.35','Owner-scoped governed skills, context, recall, compression, watchers, bounded workers, registries, and disabled heavy work');
COMMIT;
