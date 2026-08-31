BEGIN;

DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.33') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 034 requires applied schema 0.33';
 END IF;
 IF EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.34') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Schema version 0.34 is already claimed';
 END IF;
 IF (SELECT count(*) FROM li_memory.users
     WHERE user_key='christoffer' AND status='active') <> 1 THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 034 requires exactly one active owner';
 END IF;
END $$;

CREATE TABLE li_runtime_data.native_gateway_sessions(
 session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 installation_id UUID NOT NULL,
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 owner_email TEXT NOT NULL CHECK(length(owner_email)<=320),
 refresh_token_hash CHAR(64) NOT NULL UNIQUE CHECK(refresh_token_hash ~ '^[a-f0-9]{64}$'),
 previous_refresh_token_hash CHAR(64) UNIQUE
  CHECK(previous_refresh_token_hash IS NULL OR previous_refresh_token_hash ~ '^[a-f0-9]{64}$'),
 refresh_expires_at TIMESTAMPTZ NOT NULL,
 attestation_provider TEXT CHECK(attestation_provider IN
  ('apple_app_attest','apple_device_check','google_play_integrity')),
 attestation_status TEXT NOT NULL CHECK(attestation_status IN
  ('not_configured','verified','rejected')),
 revoked_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 refreshed_at TIMESTAMPTZ,
 FOREIGN KEY(owner_user_id,installation_id)
  REFERENCES li_runtime_data.mobile_location_installations(owner_user_id,installation_id)
);
CREATE TABLE li_runtime_data.native_gateway_rate_windows(
 session_id UUID NOT NULL REFERENCES li_runtime_data.native_gateway_sessions(session_id),
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 installation_id UUID NOT NULL,
 window_started_at TIMESTAMPTZ NOT NULL,
 request_count INTEGER NOT NULL CHECK(request_count>0),
 PRIMARY KEY(session_id,window_started_at),
 FOREIGN KEY(owner_user_id,installation_id)
  REFERENCES li_runtime_data.mobile_location_installations(owner_user_id,installation_id)
);
CREATE INDEX native_gateway_active_install_idx
 ON li_runtime_data.native_gateway_sessions(installation_id) WHERE revoked_at IS NULL;

ALTER TABLE li_runtime_data.native_gateway_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.native_gateway_rate_windows ENABLE ROW LEVEL SECURITY;
CREATE POLICY native_sessions_function_access ON li_runtime_data.native_gateway_sessions
 FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY native_rate_function_access ON li_runtime_data.native_gateway_rate_windows
 FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT,UPDATE,DELETE ON li_runtime_data.native_gateway_sessions,
 li_runtime_data.native_gateway_rate_windows TO li_memory_function_owner;

CREATE TEMP TABLE migration_034_authority_state(migration_role NAME,added_owner BOOLEAN,
 added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_034_authority_state SELECT CURRENT_USER,
 NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
 NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_034_authority_state) THEN
  EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I',
   (SELECT migration_role FROM migration_034_authority_state));
 END IF;
 IF (SELECT added_create FROM migration_034_authority_state) THEN
  EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner';
 END IF;
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

CREATE FUNCTION li_api.bootstrap_native_session(
 p_platform TEXT,p_owner_email TEXT,p_refresh_hash TEXT,p_refresh_expires TIMESTAMPTZ,
 p_attestation_provider TEXT,p_attestation_status TEXT
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,li_api,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_install UUID; v_session UUID;
BEGIN
 SELECT id INTO STRICT v_user FROM li_memory.users
  WHERE user_key='christoffer' AND status='active';
 IF v_user IS NULL OR lower(p_owner_email)<>'christoffer.mellden@gmail.com' OR
    p_refresh_expires<=NOW() OR p_refresh_expires>NOW()+INTERVAL '90 days' OR
    p_refresh_hash !~ '^[a-f0-9]{64}$' OR
    p_attestation_status NOT IN ('not_configured','verified','rejected') OR
    (p_attestation_status='not_configured' AND p_attestation_provider IS NOT NULL) THEN
  RAISE EXCEPTION 'Invalid native session bootstrap';
 END IF;
 PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(v_user::TEXT,3401));
 IF (SELECT count(*) FROM li_runtime_data.native_gateway_sessions
      WHERE owner_user_id=v_user AND created_at>=NOW()-INTERVAL '1 hour')>=10 THEN
  RAISE EXCEPTION 'Native session bootstrap rate limit exceeded';
 END IF;
 v_install:=li_api.register_mobile_location_installation(p_platform);
 INSERT INTO li_runtime_data.native_gateway_sessions(
  installation_id,owner_user_id,owner_email,refresh_token_hash,refresh_expires_at,
  attestation_provider,attestation_status)
 VALUES(v_install,v_user,lower(p_owner_email),p_refresh_hash,p_refresh_expires,
  p_attestation_provider,p_attestation_status) RETURNING session_id INTO v_session;
 RETURN jsonb_build_object('session_id',v_session,'installation_id',v_install,
  'attestation_status',p_attestation_status);
END $$;

CREATE FUNCTION li_api.refresh_native_session(
 p_refresh_hash TEXT,p_replacement_hash TEXT,p_refresh_expires TIMESTAMPTZ
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,pg_catalog,pg_temp AS $$
DECLARE v_session li_runtime_data.native_gateway_sessions%ROWTYPE;
BEGIN
 SELECT * INTO v_session FROM li_runtime_data.native_gateway_sessions
  WHERE refresh_token_hash=p_refresh_hash OR previous_refresh_token_hash=p_refresh_hash
  FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Expired or revoked native refresh token'; END IF;
 IF v_session.previous_refresh_token_hash=p_refresh_hash THEN
  UPDATE li_runtime_data.native_gateway_sessions SET revoked_at=COALESCE(revoked_at,NOW())
   WHERE session_id=v_session.session_id;
  UPDATE li_runtime_data.mobile_location_installations
   SET revoked_at=COALESCE(revoked_at,NOW()),permission_state='denied',updated_at=NOW()
   WHERE installation_id=v_session.installation_id AND owner_user_id=v_session.owner_user_id;
  RETURN jsonb_build_object('status','refresh_replay_detected');
 END IF;
 IF v_session.revoked_at IS NOT NULL OR v_session.refresh_expires_at<=NOW() OR
    p_replacement_hash !~ '^[a-f0-9]{64}$' OR p_refresh_expires<=NOW() OR
    p_refresh_expires>NOW()+INTERVAL '90 days' OR
    p_replacement_hash IN (v_session.refresh_token_hash,v_session.previous_refresh_token_hash) OR
    NOT EXISTS(SELECT 1 FROM li_runtime_data.mobile_location_installations
     WHERE installation_id=v_session.installation_id AND owner_user_id=v_session.owner_user_id
      AND revoked_at IS NULL) THEN
  RAISE EXCEPTION 'Expired or revoked native refresh token';
 END IF;
 UPDATE li_runtime_data.native_gateway_sessions
  SET previous_refresh_token_hash=refresh_token_hash,refresh_token_hash=p_replacement_hash,
  refresh_expires_at=p_refresh_expires,refreshed_at=NOW() WHERE session_id=v_session.session_id;
 RETURN jsonb_build_object('session_id',v_session.session_id,
  'installation_id',v_session.installation_id);
END $$;

CREATE FUNCTION li_api.validate_native_session(p_session UUID,p_installation UUID)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,pg_catalog,pg_temp AS $$
DECLARE v_session li_runtime_data.native_gateway_sessions%ROWTYPE;
 v_window TIMESTAMPTZ:=date_trunc('minute',NOW()); v_count INTEGER;
 v_install_count INTEGER; v_owner_count INTEGER;
BEGIN
 SELECT * INTO v_session FROM li_runtime_data.native_gateway_sessions
  WHERE session_id=p_session AND installation_id=p_installation;
 IF NOT FOUND OR v_session.revoked_at IS NOT NULL OR v_session.refresh_expires_at<=NOW() OR
    NOT EXISTS(SELECT 1 FROM li_runtime_data.mobile_location_installations
     WHERE installation_id=p_installation AND owner_user_id=v_session.owner_user_id
      AND revoked_at IS NULL) THEN RAISE EXCEPTION 'Invalid or revoked native session'; END IF;
 PERFORM pg_catalog.pg_advisory_xact_lock(
  pg_catalog.hashtextextended(v_session.owner_user_id::TEXT,3402));
 PERFORM pg_catalog.pg_advisory_xact_lock(
  pg_catalog.hashtextextended(v_session.installation_id::TEXT,3403));
 DELETE FROM li_runtime_data.native_gateway_rate_windows
  WHERE session_id=p_session AND window_started_at<NOW()-INTERVAL '24 hours';
 INSERT INTO li_runtime_data.native_gateway_rate_windows(
  session_id,owner_user_id,installation_id,window_started_at,request_count)
 VALUES(p_session,v_session.owner_user_id,p_installation,v_window,1)
 ON CONFLICT(session_id,window_started_at) DO UPDATE
  SET request_count=li_runtime_data.native_gateway_rate_windows.request_count+1
 RETURNING request_count INTO v_count;
 SELECT COALESCE(sum(request_count),0) INTO v_install_count
  FROM li_runtime_data.native_gateway_rate_windows
  WHERE installation_id=p_installation AND window_started_at=v_window;
 SELECT COALESCE(sum(request_count),0) INTO v_owner_count
  FROM li_runtime_data.native_gateway_rate_windows
  WHERE owner_user_id=v_session.owner_user_id AND window_started_at=v_window;
 IF v_count>120 OR v_install_count>120 OR v_owner_count>300 THEN
  RAISE EXCEPTION 'Native gateway owner, installation, or session rate limit exceeded';
 END IF;
 RETURN jsonb_build_object('status','active','session_id',p_session,
  'installation_id',v_session.installation_id);
END $$;

CREATE FUNCTION li_api.revoke_native_session(p_session UUID,p_revoke_installation BOOLEAN)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_api,pg_catalog,pg_temp AS $$
DECLARE v_install UUID;
BEGIN
 UPDATE li_runtime_data.native_gateway_sessions SET revoked_at=COALESCE(revoked_at,NOW())
  WHERE session_id=p_session RETURNING installation_id INTO v_install;
 IF NOT FOUND THEN RAISE EXCEPTION 'Native session not found'; END IF;
 IF p_revoke_installation THEN PERFORM li_api.revoke_mobile_location_installation(v_install); END IF;
 RETURN jsonb_build_object('status','revoked','installation_revoked',p_revoke_installation);
END $$;

CREATE FUNCTION li_api.revoke_all_native_sessions() RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_count INTEGER;
BEGIN
 SELECT id INTO STRICT v_user FROM li_memory.users
  WHERE user_key='christoffer' AND status='active';
 UPDATE li_runtime_data.native_gateway_sessions SET revoked_at=COALESCE(revoked_at,NOW())
  WHERE owner_user_id=v_user AND revoked_at IS NULL;
 GET DIAGNOSTICS v_count=ROW_COUNT;
 UPDATE li_runtime_data.mobile_location_installations
  SET revoked_at=COALESCE(revoked_at,NOW()),permission_state='denied',updated_at=NOW()
  WHERE owner_user_id=v_user AND revoked_at IS NULL;
 RETURN jsonb_build_object('status','revoked','session_count',v_count);
END $$;
RESET ROLE;

REVOKE ALL ON FUNCTION li_api.bootstrap_native_session(TEXT,TEXT,TEXT,TIMESTAMPTZ,TEXT,TEXT),
 li_api.refresh_native_session(TEXT,TEXT,TIMESTAMPTZ),
 li_api.validate_native_session(UUID,UUID),li_api.revoke_native_session(UUID,BOOLEAN),
 li_api.revoke_all_native_sessions() FROM PUBLIC,anon,authenticated,service_role,
 li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,
 li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.bootstrap_native_session(TEXT,TEXT,TEXT,TIMESTAMPTZ,TEXT,TEXT),
 li_api.refresh_native_session(TEXT,TEXT,TIMESTAMPTZ),
 li_api.validate_native_session(UUID,UUID),li_api.revoke_native_session(UUID,BOOLEAN),
 li_api.revoke_all_native_sessions() TO li_memory_api;
REVOKE ALL PRIVILEGES ON li_runtime_data.native_gateway_sessions,
 li_runtime_data.native_gateway_rate_windows FROM PUBLIC,anon,authenticated,service_role,
 li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,
 li_artifact_retention,li_retention_runtime;

DO $$ BEGIN
 IF (SELECT added_create FROM migration_034_authority_state) THEN
  REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
 END IF;
 IF (SELECT added_owner FROM migration_034_authority_state) THEN
  EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I',
   (SELECT migration_role FROM migration_034_authority_state));
 END IF;
 IF NOT pg_catalog.has_function_privilege('li_backend_runtime',
  'li_api.validate_native_session(uuid,uuid)','EXECUTE') THEN
  RAISE EXCEPTION 'Backend runtime lost required native session execution';
 END IF;
 IF pg_catalog.has_table_privilege('li_backend_runtime',
  'li_runtime_data.native_gateway_sessions','SELECT') THEN
  RAISE EXCEPTION 'Native gateway session table boundary is broader than intended';
 END IF;
 IF (SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r
     ON r.oid=p.proowner
     WHERE p.oid='li_api.bootstrap_native_session(text,text,text,timestamp with time zone,text,text)'::REGPROCEDURE)
    IS DISTINCT FROM 'li_memory_function_owner' OR
    (SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r
     ON r.oid=p.proowner
     WHERE p.oid='li_api.refresh_native_session(text,text,timestamp with time zone)'::REGPROCEDURE)
    IS DISTINCT FROM 'li_memory_function_owner' OR
    (SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r
     ON r.oid=p.proowner
     WHERE p.oid='li_api.validate_native_session(uuid,uuid)'::REGPROCEDURE)
    IS DISTINCT FROM 'li_memory_function_owner' THEN
  RAISE EXCEPTION 'Native gateway function has unexpected owner';
 END IF;
 IF (SELECT added_create FROM migration_034_authority_state) AND
    pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN
  RAISE EXCEPTION 'Temporary li_api CREATE authority was not removed';
 END IF;
 IF (SELECT added_owner FROM migration_034_authority_state) AND
    (pg_catalog.pg_has_role((SELECT migration_role FROM migration_034_authority_state),
      'li_memory_function_owner','SET') OR
     pg_catalog.pg_has_role((SELECT migration_role FROM migration_034_authority_state),
      'li_memory_function_owner','USAGE')) THEN
  RAISE EXCEPTION 'Temporary function-owner authority was not removed';
 END IF;
END $$;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.34','Authenticated native gateway sessions, hashed refresh rotation, revocation, and rate limiting');
COMMIT;
