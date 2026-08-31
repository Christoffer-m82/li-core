BEGIN;

DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.32') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 033 requires applied schema 0.32';
 END IF;
 IF EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.33') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Schema version 0.33 is already claimed';
 END IF;
 IF (SELECT count(*) FROM li_memory.users WHERE user_key='christoffer' AND status='active') <> 1 THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 033 requires exactly one active owner';
 END IF;
END $$;

CREATE TABLE li_runtime_data.mobile_location_installations(
 installation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 platform TEXT NOT NULL CHECK(platform IN ('ios','android')),
 permission_state TEXT NOT NULL DEFAULT 'not_requested'
  CHECK(permission_state IN ('unknown','not_requested','denied','granted','restricted')),
 revoked_at TIMESTAMPTZ,
 last_accepted_observed_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(owner_user_id,installation_id)
);
CREATE TABLE li_runtime_data.mobile_location_updates(
 update_id UUID PRIMARY KEY, installation_id UUID NOT NULL,
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), contract_version TEXT NOT NULL CHECK(contract_version='1.0'),
 country_code CHAR(2) NOT NULL CHECK(country_code ~ '^[A-Z]{2}$'), town_city TEXT CHECK(length(town_city)<=120),
 source TEXT NOT NULL CHECK(source='device_coarse'), observed_at TIMESTAMPTZ NOT NULL,
 permission_state TEXT NOT NULL CHECK(permission_state='granted'), permission_checked_at TIMESTAMPTZ NOT NULL,
 accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), applied_to_current_place BOOLEAN NOT NULL,
 UNIQUE(update_id,owner_user_id),
 FOREIGN KEY(owner_user_id,installation_id) REFERENCES li_runtime_data.mobile_location_installations(owner_user_id,installation_id)
);
CREATE TABLE li_runtime_data.mobile_location_visit_events(
 event_id UUID PRIMARY KEY, update_id UUID NOT NULL,
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), country_code CHAR(2) NOT NULL CHECK(country_code ~ '^[A-Z]{2}$'),
 first_observed_at TIMESTAMPTZ NOT NULL, last_observed_at TIMESTAMPTZ NOT NULL CHECK(last_observed_at>=first_observed_at),
 classification TEXT NOT NULL CHECK(classification IN ('overnight','transit')), corrected_at TIMESTAMPTZ,
 CHECK(classification<>'overnight' OR last_observed_at::date>first_observed_at::date),
 FOREIGN KEY(update_id,owner_user_id) REFERENCES li_runtime_data.mobile_location_updates(update_id,owner_user_id)
);
CREATE INDEX mobile_location_rate_idx ON li_runtime_data.mobile_location_updates(installation_id,accepted_at DESC);
ALTER TABLE li_runtime_data.mobile_location_installations ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.mobile_location_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.mobile_location_visit_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY mobile_installations_function_access ON li_runtime_data.mobile_location_installations FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY mobile_updates_function_access ON li_runtime_data.mobile_location_updates FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY mobile_visits_function_access ON li_runtime_data.mobile_location_visit_events FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT,UPDATE ON li_runtime_data.mobile_location_installations,li_runtime_data.mobile_location_updates,li_runtime_data.mobile_location_visit_events TO li_memory_function_owner;

CREATE TEMP TABLE migration_033_authority_state(migration_role NAME,added_owner BOOLEAN,added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_033_authority_state SELECT CURRENT_USER,
 NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
 NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_033_authority_state) THEN EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I',(SELECT migration_role FROM migration_033_authority_state)); END IF;
 IF (SELECT added_create FROM migration_033_authority_state) THEN EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner'; END IF;
END $$;
DO $$ BEGIN
 IF NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET') THEN
  RAISE EXCEPTION 'Migration role cannot assume li_memory_function_owner';
 END IF;
 IF NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN
  RAISE EXCEPTION 'Function owner cannot create in li_api';
 END IF;
END $$;
SET LOCAL ROLE li_memory_function_owner;

CREATE OR REPLACE FUNCTION li_api.get_place_settings() RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 RETURN jsonb_build_object(
  'current_place',COALESCE((SELECT jsonb_build_object('country_code',country_code,'town_city',town_city,'source',source,'provider_permission',provider_permission) FROM li_runtime_data.place_settings WHERE owner_user_id=v_user),'{}'::jsonb),
  'most_visited',COALESCE((SELECT jsonb_agg(jsonb_build_object('country_code',p.country_code,'state',p.state) ORDER BY CASE p.state WHEN 'pinned' THEN 0 ELSE 1 END,p.updated_at) FROM li_runtime_data.place_country_preferences p WHERE p.owner_user_id=v_user AND (p.state='pinned' OR (p.state='automatic' AND (SELECT count(*) FROM li_runtime_data.place_visits v WHERE v.owner_user_id=v_user AND v.country_code=p.country_code AND v.overnight_confirmed AND v.last_seen>v.first_seen AND v.last_seen>=CURRENT_DATE-365)>=2))),'[]'::jsonb),
  'provider',jsonb_build_object('web_location_mode','manual','native_automatic_updates_shipped',false,'connected_native_providers',(SELECT count(*) FROM li_runtime_data.mobile_location_installations WHERE owner_user_id=v_user AND revoked_at IS NULL),'installations',COALESCE((SELECT jsonb_agg(jsonb_build_object('installation_id',installation_id,'platform',platform,'permission_state',permission_state,'last_accepted_coarse_update',last_accepted_observed_at) ORDER BY updated_at DESC) FROM li_runtime_data.mobile_location_installations WHERE owner_user_id=v_user AND revoked_at IS NULL),'[]'::jsonb),'permission_state',COALESCE((SELECT permission_state FROM li_runtime_data.mobile_location_installations WHERE owner_user_id=v_user AND revoked_at IS NULL ORDER BY updated_at DESC LIMIT 1),'not_configured'),'last_accepted_coarse_update',(SELECT max(last_accepted_observed_at) FROM li_runtime_data.mobile_location_installations WHERE owner_user_id=v_user AND revoked_at IS NULL),'precise_coordinates_persisted',false),
  'privacy',jsonb_build_object('visit_history_shared_with_specialists',false,'continuous_location_stored',false)
 ); END $$;

CREATE FUNCTION li_api.register_mobile_location_installation(p_platform TEXT) RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; v_id UUID; BEGIN
 IF p_platform NOT IN ('ios','android') THEN RAISE EXCEPTION 'Invalid mobile platform'; END IF;
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 INSERT INTO li_runtime_data.mobile_location_installations(owner_user_id,platform) VALUES(v_user,p_platform) RETURNING installation_id INTO v_id;
 RETURN v_id; END $$;

CREATE FUNCTION li_api.submit_mobile_location_update(p_update UUID,p_installation UUID,p_country TEXT,p_town TEXT,p_observed TIMESTAMPTZ,p_permission TEXT,p_permission_checked TIMESTAMPTZ,p_event UUID DEFAULT NULL,p_first TIMESTAMPTZ DEFAULT NULL,p_last TIMESTAMPTZ DEFAULT NULL,p_classification TEXT DEFAULT NULL) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; v_applied BOOLEAN:=FALSE; v_source TEXT; v_updated TIMESTAMPTZ; v_last_observed TIMESTAMPTZ; BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 IF NOT EXISTS(SELECT 1 FROM li_runtime_data.mobile_location_installations WHERE installation_id=p_installation AND owner_user_id=v_user AND revoked_at IS NULL) THEN RAISE EXCEPTION 'Unknown or revoked installation'; END IF;
 IF EXISTS(SELECT 1 FROM li_runtime_data.mobile_location_updates WHERE update_id=p_update AND installation_id=p_installation AND owner_user_id=v_user) THEN RETURN jsonb_build_object('status','idempotent','settings',li_api.get_place_settings()); END IF;
 IF EXISTS(SELECT 1 FROM li_runtime_data.mobile_location_updates WHERE update_id=p_update) THEN RAISE EXCEPTION 'Update identifier is already bound'; END IF;
 IF p_country !~ '^[A-Z]{2}$' OR p_permission<>'granted' OR p_permission_checked<p_observed-INTERVAL '24 hours' OR p_permission_checked>p_observed+INTERVAL '5 minutes' OR p_observed<NOW()-INTERVAL '24 hours' OR p_observed>NOW()+INTERVAL '5 minutes' THEN RAISE EXCEPTION 'Invalid, stale, or unpermitted coarse observation'; END IF;
 IF p_town IS NOT NULL AND length(btrim(p_town))>120 THEN RAISE EXCEPTION 'Town/city is too long'; END IF;
 IF (p_event IS NULL) <> (p_first IS NULL) OR (p_event IS NULL) <> (p_last IS NULL) OR (p_event IS NULL) <> (p_classification IS NULL) THEN RAISE EXCEPTION 'Visit event fields must be supplied together'; END IF;
 SELECT last_accepted_observed_at INTO v_last_observed FROM li_runtime_data.mobile_location_installations WHERE installation_id=p_installation FOR UPDATE;
 IF (SELECT count(*) FROM li_runtime_data.mobile_location_updates WHERE installation_id=p_installation AND accepted_at>=NOW()-INTERVAL '1 hour')>=30 THEN RAISE EXCEPTION 'Mobile location update limit exceeded'; END IF;
 IF v_last_observed IS NOT NULL AND p_observed<=v_last_observed THEN RAISE EXCEPTION 'Out-of-order coarse observation'; END IF;
 SELECT source,updated_at INTO v_source,v_updated FROM li_runtime_data.place_settings WHERE owner_user_id=v_user;
 v_applied:=v_source IS NULL OR v_source='device_coarse' OR p_observed>=v_updated+INTERVAL '24 hours';
 INSERT INTO li_runtime_data.mobile_location_updates(update_id,installation_id,owner_user_id,contract_version,country_code,town_city,source,observed_at,permission_state,permission_checked_at,applied_to_current_place) VALUES(p_update,p_installation,v_user,'1.0',p_country,NULLIF(btrim(p_town),''),'device_coarse',p_observed,p_permission,p_permission_checked,v_applied);
 UPDATE li_runtime_data.mobile_location_installations SET permission_state=p_permission,last_accepted_observed_at=p_observed,updated_at=NOW() WHERE installation_id=p_installation;
 IF v_applied THEN INSERT INTO li_runtime_data.place_settings(owner_user_id,country_code,town_city,source,provider_permission,updated_at) VALUES(v_user,p_country,NULLIF(btrim(p_town),''),'device_coarse','granted',p_observed) ON CONFLICT(owner_user_id) DO UPDATE SET country_code=EXCLUDED.country_code,town_city=EXCLUDED.town_city,source=EXCLUDED.source,provider_permission=EXCLUDED.provider_permission,updated_at=EXCLUDED.updated_at; END IF;
 IF p_event IS NOT NULL THEN
  IF p_classification NOT IN ('overnight','transit') OR p_last<p_first OR p_last>p_observed OR (p_classification='overnight' AND p_last::date<=p_first::date) THEN RAISE EXCEPTION 'Invalid visit event'; END IF;
  INSERT INTO li_runtime_data.mobile_location_visit_events(event_id,update_id,owner_user_id,country_code,first_observed_at,last_observed_at,classification) VALUES(p_event,p_update,v_user,p_country,p_first,p_last,p_classification);
  PERFORM li_api.add_place_visit(p_country,p_first::date,p_last::date,p_classification='overnight','device_coarse');
 END IF;
 RETURN jsonb_build_object('status','accepted','applied_to_current_place',v_applied,'settings',li_api.get_place_settings()); END $$;

CREATE FUNCTION li_api.correct_mobile_location_visit(p_installation UUID,p_event UUID,p_classification TEXT) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; v_event li_runtime_data.mobile_location_visit_events%ROWTYPE; v_replay RECORD; BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 IF p_classification NOT IN ('overnight','transit') OR NOT EXISTS(SELECT 1 FROM li_runtime_data.mobile_location_installations WHERE installation_id=p_installation AND owner_user_id=v_user AND revoked_at IS NULL) THEN RAISE EXCEPTION 'Invalid correction'; END IF;
 SELECT e.* INTO v_event FROM li_runtime_data.mobile_location_visit_events e JOIN li_runtime_data.mobile_location_updates u ON u.update_id=e.update_id WHERE e.event_id=p_event AND e.owner_user_id=v_user AND u.installation_id=p_installation;
 IF NOT FOUND THEN RAISE EXCEPTION 'Visit event not found'; END IF;
 UPDATE li_runtime_data.mobile_location_visit_events SET classification=p_classification,corrected_at=NOW() WHERE event_id=p_event;
 DELETE FROM li_runtime_data.place_visits WHERE owner_user_id=v_user AND country_code=v_event.country_code AND source='device_coarse';
 FOR v_replay IN SELECT first_observed_at,last_observed_at,classification FROM li_runtime_data.mobile_location_visit_events WHERE owner_user_id=v_user AND country_code=v_event.country_code ORDER BY first_observed_at LOOP
  PERFORM li_api.add_place_visit(v_event.country_code,v_replay.first_observed_at::date,v_replay.last_observed_at::date,v_replay.classification='overnight','device_coarse');
 END LOOP;
 RETURN li_api.get_place_settings(); END $$;

CREATE FUNCTION li_api.revoke_mobile_location_installation(p_installation UUID) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 UPDATE li_runtime_data.mobile_location_installations SET revoked_at=NOW(),permission_state='denied',updated_at=NOW() WHERE installation_id=p_installation AND owner_user_id=v_user AND revoked_at IS NULL;
 IF NOT FOUND THEN RAISE EXCEPTION 'Installation not found or already revoked'; END IF;
 RETURN li_api.get_place_settings(); END $$;
RESET ROLE;

REVOKE ALL ON FUNCTION li_api.register_mobile_location_installation(TEXT),li_api.submit_mobile_location_update(UUID,UUID,TEXT,TEXT,TIMESTAMPTZ,TEXT,TIMESTAMPTZ,UUID,TIMESTAMPTZ,TIMESTAMPTZ,TEXT),li_api.correct_mobile_location_visit(UUID,UUID,TEXT),li_api.revoke_mobile_location_installation(UUID) FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.register_mobile_location_installation(TEXT),li_api.submit_mobile_location_update(UUID,UUID,TEXT,TEXT,TIMESTAMPTZ,TEXT,TIMESTAMPTZ,UUID,TIMESTAMPTZ,TIMESTAMPTZ,TEXT),li_api.correct_mobile_location_visit(UUID,UUID,TEXT),li_api.revoke_mobile_location_installation(UUID) TO li_memory_api;
REVOKE ALL PRIVILEGES ON li_runtime_data.mobile_location_installations,li_runtime_data.mobile_location_updates,li_runtime_data.mobile_location_visit_events FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
DO $$
DECLARE function_name TEXT;
BEGIN
 IF (SELECT added_create FROM migration_033_authority_state) THEN REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner; END IF;
 IF (SELECT added_owner FROM migration_033_authority_state) THEN EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I',(SELECT migration_role FROM migration_033_authority_state)); END IF;
 FOREACH function_name IN ARRAY ARRAY['li_api.get_place_settings()','li_api.register_mobile_location_installation(text)','li_api.submit_mobile_location_update(uuid,uuid,text,text,timestamp with time zone,text,timestamp with time zone,uuid,timestamp with time zone,timestamp with time zone,text)','li_api.correct_mobile_location_visit(uuid,uuid,text)','li_api.revoke_mobile_location_installation(uuid)'] LOOP
  IF (SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner WHERE p.oid=function_name::REGPROCEDURE) IS DISTINCT FROM 'li_memory_function_owner' THEN RAISE EXCEPTION 'Function % has unexpected owner',function_name; END IF;
 END LOOP;
 IF NOT pg_catalog.has_function_privilege('li_backend_runtime','li_api.submit_mobile_location_update(uuid,uuid,text,text,timestamp with time zone,text,timestamp with time zone,uuid,timestamp with time zone,timestamp with time zone,text)','EXECUTE') THEN RAISE EXCEPTION 'Backend runtime lost required mobile Place execution'; END IF;
 IF pg_catalog.has_table_privilege('li_backend_runtime','li_runtime_data.mobile_location_updates','SELECT') OR pg_catalog.has_function_privilege('li_retention_runtime','li_api.submit_mobile_location_update(uuid,uuid,text,text,timestamp with time zone,text,timestamp with time zone,uuid,timestamp with time zone,timestamp with time zone,text)','EXECUTE') THEN RAISE EXCEPTION 'Mobile Place privilege boundary is broader than intended'; END IF;
 IF (SELECT added_create FROM migration_033_authority_state) AND pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN RAISE EXCEPTION 'Temporary li_api CREATE authority was not removed'; END IF;
 IF (SELECT added_owner FROM migration_033_authority_state) AND (pg_catalog.pg_has_role((SELECT migration_role FROM migration_033_authority_state),'li_memory_function_owner','SET') OR pg_catalog.pg_has_role((SELECT migration_role FROM migration_033_authority_state),'li_memory_function_owner','USAGE')) THEN RAISE EXCEPTION 'Temporary function-owner authority was not removed'; END IF;
END $$;
INSERT INTO li_memory.schema_versions(version,description) VALUES('0.33','Opaque native location installations, replay protection, revocation, and coarse provider status');
COMMIT;
