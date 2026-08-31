BEGIN;

DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.31') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 032 requires applied schema 0.31';
 END IF;
 IF EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.32') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Schema version 0.32 is already claimed';
 END IF;
END $$;

CREATE TABLE li_runtime_data.place_settings(
 owner_user_id UUID PRIMARY KEY REFERENCES li_memory.users(id),
 country_code CHAR(2) CHECK(country_code ~ '^[A-Z]{2}$'),
 town_city TEXT CHECK(length(town_city)<=120),
 source TEXT NOT NULL DEFAULT 'manual_web' CHECK(source IN ('manual_web','manual_mobile','device_coarse')),
 provider_permission TEXT NOT NULL DEFAULT 'not_applicable' CHECK(provider_permission IN ('not_applicable','not_requested','denied','granted')),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE li_runtime_data.place_country_preferences(
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id), country_code CHAR(2) NOT NULL CHECK(country_code ~ '^[A-Z]{2}$'),
 state TEXT NOT NULL CHECK(state IN ('automatic','pinned','suppressed')), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 PRIMARY KEY(owner_user_id,country_code)
);
CREATE TABLE li_runtime_data.place_visits(
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 country_code CHAR(2) NOT NULL CHECK(country_code ~ '^[A-Z]{2}$'), first_seen DATE NOT NULL,
 last_seen DATE NOT NULL CHECK(last_seen>=first_seen), overnight_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
 source TEXT NOT NULL CHECK(source IN ('manual','device_coarse')), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(owner_user_id,country_code,first_seen,last_seen)
);
CREATE INDEX place_visits_eligibility_idx ON li_runtime_data.place_visits(owner_user_id,country_code,last_seen DESC) WHERE overnight_confirmed;
ALTER TABLE li_runtime_data.place_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.place_country_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.place_visits ENABLE ROW LEVEL SECURITY;
CREATE POLICY place_settings_function_access ON li_runtime_data.place_settings FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY place_preferences_function_access ON li_runtime_data.place_country_preferences FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY place_visits_function_access ON li_runtime_data.place_visits FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT,UPDATE ON li_runtime_data.place_settings,li_runtime_data.place_country_preferences,li_runtime_data.place_visits TO li_memory_function_owner;

CREATE TEMP TABLE migration_032_authority_state(migration_role NAME,added_owner BOOLEAN,added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_032_authority_state SELECT CURRENT_USER,
 NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
 NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_032_authority_state) THEN EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I',(SELECT migration_role FROM migration_032_authority_state)); END IF;
 IF (SELECT added_create FROM migration_032_authority_state) THEN EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner'; END IF;
END $$;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.get_place_settings() RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 RETURN jsonb_build_object(
  'current_place',COALESCE((SELECT jsonb_build_object('country_code',country_code,'town_city',town_city,'source',source,'provider_permission',provider_permission) FROM li_runtime_data.place_settings WHERE owner_user_id=v_user),'{}'::jsonb),
  'most_visited',COALESCE((SELECT jsonb_agg(jsonb_build_object('country_code',country_code,'state',state) ORDER BY CASE state WHEN 'pinned' THEN 0 ELSE 1 END,updated_at) FROM li_runtime_data.place_country_preferences WHERE owner_user_id=v_user AND state IN ('pinned','automatic')),'[]'::jsonb),
  'provider',jsonb_build_object('kind','manual_web','permission_state','not_applicable','precise_coordinates_persisted',false),
  'privacy',jsonb_build_object('visit_history_shared_with_specialists',false,'continuous_location_stored',false)
 ); END $$;
CREATE FUNCTION li_api.set_current_place(p_country TEXT,p_town TEXT,p_source TEXT,p_permission TEXT) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; BEGIN
 IF p_country IS NOT NULL AND p_country !~ '^[A-Z]{2}$' THEN RAISE EXCEPTION 'Invalid country'; END IF;
 IF p_source NOT IN ('manual_web','manual_mobile','device_coarse') OR p_permission NOT IN ('not_applicable','not_requested','denied','granted') THEN RAISE EXCEPTION 'Invalid provider metadata'; END IF;
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 INSERT INTO li_runtime_data.place_settings(owner_user_id,country_code,town_city,source,provider_permission) VALUES(v_user,p_country,NULLIF(btrim(p_town),''),p_source,p_permission)
 ON CONFLICT(owner_user_id) DO UPDATE SET country_code=EXCLUDED.country_code,town_city=EXCLUDED.town_city,source=EXCLUDED.source,provider_permission=EXCLUDED.provider_permission,updated_at=NOW();
 RETURN li_api.get_place_settings(); END $$;
CREATE FUNCTION li_api.set_most_visited_preference(p_country TEXT,p_action TEXT) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; BEGIN
 IF p_country !~ '^[A-Z]{2}$' OR p_action NOT IN ('pin','remove') THEN RAISE EXCEPTION 'Invalid preference'; END IF;
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 INSERT INTO li_runtime_data.place_country_preferences(owner_user_id,country_code,state) VALUES(v_user,p_country,CASE WHEN p_action='pin' THEN 'pinned' ELSE 'suppressed' END)
 ON CONFLICT(owner_user_id,country_code) DO UPDATE SET state=EXCLUDED.state,updated_at=NOW();
 RETURN li_api.get_place_settings(); END $$;
CREATE FUNCTION li_api.add_place_visit(p_country TEXT,p_first DATE,p_last DATE,p_overnight BOOLEAN,p_source TEXT) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$ DECLARE v_user UUID; v_visits INTEGER; BEGIN
 IF p_country !~ '^[A-Z]{2}$' OR p_last<p_first OR p_source NOT IN ('manual','device_coarse') THEN RAISE EXCEPTION 'Invalid visit'; END IF;
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 INSERT INTO li_runtime_data.place_visits(owner_user_id,country_code,first_seen,last_seen,overnight_confirmed,source) VALUES(v_user,p_country,p_first,p_last,p_overnight,p_source)
 ON CONFLICT(owner_user_id,country_code,first_seen,last_seen) DO UPDATE SET overnight_confirmed=EXCLUDED.overnight_confirmed,source=EXCLUDED.source;
 SELECT count(DISTINCT (first_seen,last_seen)) INTO v_visits FROM li_runtime_data.place_visits WHERE owner_user_id=v_user AND country_code=p_country AND overnight_confirmed AND last_seen>=CURRENT_DATE-365;
 IF v_visits>=2 AND NOT EXISTS(SELECT 1 FROM li_runtime_data.place_country_preferences WHERE owner_user_id=v_user AND country_code=p_country AND state='suppressed') THEN
  INSERT INTO li_runtime_data.place_country_preferences(owner_user_id,country_code,state) VALUES(v_user,p_country,'automatic') ON CONFLICT(owner_user_id,country_code) DO UPDATE SET state=CASE WHEN li_runtime_data.place_country_preferences.state='pinned' THEN 'pinned' ELSE 'automatic' END,updated_at=NOW();
 END IF;
 RETURN li_api.get_place_settings(); END $$;
REVOKE ALL ON FUNCTION li_api.get_place_settings(),li_api.set_current_place(TEXT,TEXT,TEXT,TEXT),li_api.set_most_visited_preference(TEXT,TEXT),li_api.add_place_visit(TEXT,DATE,DATE,BOOLEAN,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION li_api.get_place_settings(),li_api.set_current_place(TEXT,TEXT,TEXT,TEXT),li_api.set_most_visited_preference(TEXT,TEXT),li_api.add_place_visit(TEXT,DATE,DATE,BOOLEAN,TEXT) TO li_backend_runtime;
RESET ROLE;
DO $$ BEGIN
 IF (SELECT added_create FROM migration_032_authority_state) THEN REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner; END IF;
 IF (SELECT added_owner FROM migration_032_authority_state) THEN EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I',(SELECT migration_role FROM migration_032_authority_state)); END IF;
END $$;
INSERT INTO li_memory.schema_versions(version,description) VALUES('0.32','Private current place, minimal visit events, and most-visited preferences');
COMMIT;
