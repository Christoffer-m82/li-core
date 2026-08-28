BEGIN;

GRANT li_memory_function_owner TO postgres;
GRANT USAGE, CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE OR REPLACE FUNCTION li_api.replace_agent_recommendations(p_items JSONB)
RETURNS TABLE(recommendation_id UUID,subject_agent TEXT,action TEXT,rationale TEXT,status TEXT)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID;
BEGIN
  SELECT u.id INTO v_user
  FROM li_memory.users AS u
  WHERE u.user_key='christoffer' AND u.status='active'
  LIMIT 1;

  INSERT INTO li_runtime_data.agent_recommendations(
    owner_user_id,subject_agent,action,rationale,evidence
  )
  SELECT v_user,x->>'subject_agent',x->>'action',x->>'rationale',x
  FROM jsonb_array_elements(p_items) x;

  RETURN QUERY
  SELECT r.id,r.subject_agent,r.action,r.rationale,r.status
  FROM li_runtime_data.agent_recommendations r
  WHERE r.owner_user_id=v_user AND r.status='pending_approval'
  ORDER BY r.created_at DESC;
END;
$$;

CREATE OR REPLACE FUNCTION li_api.review_agent_recommendation(p_id UUID,p_decision TEXT)
RETURNS TABLE(recommendation_id UUID,subject_agent TEXT,action TEXT,status TEXT)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID;
BEGIN
  IF p_decision NOT IN ('approve','reject') THEN
    RAISE EXCEPTION 'Invalid decision';
  END IF;

  SELECT u.id INTO v_user
  FROM li_memory.users AS u
  WHERE u.user_key='christoffer' AND u.status='active'
  LIMIT 1;

  UPDATE li_runtime_data.agent_recommendations r
  SET status=CASE
      WHEN p_decision='approve' THEN 'approved_pending_execution'
      ELSE 'rejected'
    END,
    reviewed_at=NOW()
  WHERE r.id=p_id AND r.owner_user_id=v_user AND r.status='pending_approval';

  RETURN QUERY
  SELECT r.id,r.subject_agent,r.action,r.status
  FROM li_runtime_data.agent_recommendations r
  WHERE r.id=p_id AND r.owner_user_id=v_user;
END;
$$;

RESET ROLE;

REVOKE ALL ON FUNCTION li_api.replace_agent_recommendations(JSONB),
  li_api.review_agent_recommendation(UUID,TEXT)
  FROM PUBLIC,anon,authenticated,service_role,li_memory_theo,
  li_memory_owner_confirmation;
GRANT EXECUTE ON FUNCTION li_api.replace_agent_recommendations(JSONB),
  li_api.review_agent_recommendation(UUID,TEXT)
  TO li_memory_api;
REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.19','Fix agent recommendation status column ambiguity')
ON CONFLICT(version) DO NOTHING;

COMMIT;
