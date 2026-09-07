BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.41') THEN
    RAISE EXCEPTION USING ERRCODE = '55000',
      MESSAGE = 'Migration 042 requires applied schema 0.41';
  END IF;
  IF EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.42') THEN
    RAISE EXCEPTION USING ERRCODE = '55000',
      MESSAGE = 'Schema version 0.42 is already claimed';
  END IF;
  IF (SELECT COUNT(*) FROM li_memory.users
      WHERE user_key = 'christoffer' AND status = 'active') <> 1 THEN
    RAISE EXCEPTION 'Migration 042 requires exactly one active owner';
  END IF;
END $$;

CREATE TABLE li_runtime_data.portfolio_holdings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
  account_kind TEXT NOT NULL CHECK (account_kind IN ('avanza', 'crypto')),
  symbol TEXT NOT NULL CHECK (symbol ~ '^[A-Z0-9][A-Z0-9.-]{0,23}$'),
  asset_name TEXT NOT NULL CHECK (length(asset_name) BETWEEN 1 AND 120),
  quantity NUMERIC(30,12) NOT NULL CHECK (quantity > 0),
  average_unit_cost NUMERIC(30,8) NOT NULL CHECK (average_unit_cost >= 0),
  cost_currency CHAR(3) NOT NULL CHECK (cost_currency ~ '^[A-Z]{3}$'),
  current_unit_price NUMERIC(30,8) CHECK (current_unit_price >= 0),
  quote_currency CHAR(3) CHECK (quote_currency ~ '^[A-Z]{3}$'),
  price_as_of TIMESTAMPTZ,
  quote_source TEXT CHECK (quote_source IN ('owner_manual')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  archived_at TIMESTAMPTZ,
  CHECK (
    (current_unit_price IS NULL AND quote_currency IS NULL
      AND price_as_of IS NULL AND quote_source IS NULL)
    OR
    (current_unit_price IS NOT NULL AND quote_currency IS NOT NULL
      AND price_as_of IS NOT NULL AND quote_source = 'owner_manual')
  )
);

CREATE UNIQUE INDEX portfolio_holdings_active_symbol_idx
ON li_runtime_data.portfolio_holdings(owner_user_id, account_kind, symbol)
WHERE archived_at IS NULL;

ALTER TABLE li_runtime_data.portfolio_holdings ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.portfolio_holdings FORCE ROW LEVEL SECURITY;
CREATE POLICY portfolio_holdings_function_access
ON li_runtime_data.portfolio_holdings FOR ALL TO li_memory_function_owner
USING (TRUE) WITH CHECK (TRUE);
GRANT SELECT, INSERT, UPDATE ON li_runtime_data.portfolio_holdings
TO li_memory_function_owner;

CREATE TEMP TABLE migration_042_authority_state (
  migration_role NAME NOT NULL,
  added_owner BOOLEAN NOT NULL,
  added_create BOOLEAN NOT NULL
) ON COMMIT DROP;

INSERT INTO migration_042_authority_state
SELECT CURRENT_USER,
  NOT pg_catalog.pg_has_role(CURRENT_USER, 'li_memory_function_owner', 'SET'),
  NOT pg_catalog.has_schema_privilege('li_memory_function_owner', 'li_api', 'CREATE');

DO $$
DECLARE role_name NAME := (SELECT migration_role FROM migration_042_authority_state);
BEGIN
  IF (SELECT added_owner FROM migration_042_authority_state) THEN
    EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I', role_name);
  END IF;
  IF (SELECT added_create FROM migration_042_authority_state) THEN
    EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner';
  END IF;
END $$;

SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.list_portfolio_holdings(p_account TEXT DEFAULT NULL)
RETURNS TABLE (
  holding_id UUID,
  account TEXT,
  symbol TEXT,
  asset_name TEXT,
  quantity NUMERIC,
  average_unit_cost NUMERIC,
  cost_currency TEXT,
  current_unit_price NUMERIC,
  quote_currency TEXT,
  price_as_of TIMESTAMPTZ,
  quote_source TEXT
) LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID;
BEGIN
  IF p_account IS NOT NULL AND p_account NOT IN ('avanza', 'crypto') THEN
    RAISE EXCEPTION 'Invalid portfolio account';
  END IF;
  SELECT id INTO STRICT v_user FROM li_memory.users
  WHERE user_key = 'christoffer' AND status = 'active';
  RETURN QUERY
  SELECT h.id, h.account_kind, h.symbol, h.asset_name, h.quantity,
    h.average_unit_cost, h.cost_currency::TEXT, h.current_unit_price,
    h.quote_currency::TEXT, h.price_as_of, h.quote_source
  FROM li_runtime_data.portfolio_holdings h
  WHERE h.owner_user_id = v_user AND h.archived_at IS NULL
    AND (p_account IS NULL OR h.account_kind = p_account)
  ORDER BY h.account_kind, h.asset_name, h.symbol;
END $$;

CREATE FUNCTION li_api.upsert_portfolio_holding(
  p_id UUID,
  p_account TEXT,
  p_symbol TEXT,
  p_asset_name TEXT,
  p_quantity NUMERIC,
  p_average_unit_cost NUMERIC,
  p_cost_currency TEXT,
  p_current_unit_price NUMERIC,
  p_quote_currency TEXT
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID; h li_runtime_data.portfolio_holdings%ROWTYPE;
BEGIN
  p_symbol := upper(btrim(p_symbol));
  p_asset_name := btrim(p_asset_name);
  p_cost_currency := upper(btrim(p_cost_currency));
  p_quote_currency := CASE WHEN p_quote_currency IS NULL THEN NULL
    ELSE upper(btrim(p_quote_currency)) END;
  IF p_account NOT IN ('avanza', 'crypto')
    OR p_symbol !~ '^[A-Z0-9][A-Z0-9.-]{0,23}$'
    OR length(p_asset_name) NOT BETWEEN 1 AND 120
    OR p_quantity <= 0 OR p_average_unit_cost < 0
    OR p_cost_currency !~ '^[A-Z]{3}$'
    OR (p_current_unit_price IS NULL) <> (p_quote_currency IS NULL)
    OR p_current_unit_price < 0
    OR (p_quote_currency IS NOT NULL AND p_quote_currency !~ '^[A-Z]{3}$') THEN
    RAISE EXCEPTION 'Invalid portfolio holding';
  END IF;
  SELECT id INTO STRICT v_user FROM li_memory.users
  WHERE user_key = 'christoffer' AND status = 'active';
  IF p_id IS NULL THEN
    INSERT INTO li_runtime_data.portfolio_holdings(
      owner_user_id, account_kind, symbol, asset_name, quantity,
      average_unit_cost, cost_currency, current_unit_price, quote_currency,
      price_as_of, quote_source
    ) VALUES (
      v_user, p_account, p_symbol, p_asset_name, p_quantity,
      p_average_unit_cost, p_cost_currency, p_current_unit_price, p_quote_currency,
      CASE WHEN p_current_unit_price IS NULL THEN NULL ELSE NOW() END,
      CASE WHEN p_current_unit_price IS NULL THEN NULL ELSE 'owner_manual' END
    ) RETURNING * INTO h;
  ELSE
    UPDATE li_runtime_data.portfolio_holdings SET
      account_kind = p_account,
      symbol = p_symbol,
      asset_name = p_asset_name,
      quantity = p_quantity,
      average_unit_cost = p_average_unit_cost,
      cost_currency = p_cost_currency,
      current_unit_price = p_current_unit_price,
      quote_currency = p_quote_currency,
      price_as_of = CASE WHEN p_current_unit_price IS NULL THEN NULL ELSE NOW() END,
      quote_source = CASE WHEN p_current_unit_price IS NULL THEN NULL ELSE 'owner_manual' END,
      updated_at = NOW()
    WHERE id = p_id AND owner_user_id = v_user AND archived_at IS NULL
    RETURNING * INTO h;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'Portfolio holding not found';
    END IF;
  END IF;
  RETURN jsonb_build_object(
    'holding_id', h.id,
    'account', h.account_kind,
    'symbol', h.symbol,
    'asset_name', h.asset_name,
    'quantity', h.quantity,
    'average_unit_cost', h.average_unit_cost,
    'cost_currency', h.cost_currency,
    'current_unit_price', h.current_unit_price,
    'quote_currency', h.quote_currency,
    'price_as_of', h.price_as_of,
    'quote_source', h.quote_source
  );
END $$;

CREATE FUNCTION li_api.archive_portfolio_holding(p_id UUID)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID; changed INTEGER;
BEGIN
  SELECT id INTO STRICT v_user FROM li_memory.users
  WHERE user_key = 'christoffer' AND status = 'active';
  UPDATE li_runtime_data.portfolio_holdings
  SET archived_at = NOW(), updated_at = NOW()
  WHERE id = p_id AND owner_user_id = v_user AND archived_at IS NULL;
  GET DIAGNOSTICS changed = ROW_COUNT;
  RETURN changed = 1;
END $$;

RESET ROLE;

REVOKE ALL ON FUNCTION
  li_api.list_portfolio_holdings(TEXT),
  li_api.upsert_portfolio_holding(UUID,TEXT,TEXT,TEXT,NUMERIC,NUMERIC,TEXT,NUMERIC,TEXT),
  li_api.archive_portfolio_holding(UUID)
FROM PUBLIC, anon, authenticated, service_role, li_backend_runtime, li_memory_api,
  li_memory_theo, li_memory_owner_confirmation, li_artifact_retention,
  li_retention_runtime;
GRANT EXECUTE ON FUNCTION
  li_api.list_portfolio_holdings(TEXT),
  li_api.upsert_portfolio_holding(UUID,TEXT,TEXT,TEXT,NUMERIC,NUMERIC,TEXT,NUMERIC,TEXT),
  li_api.archive_portfolio_holding(UUID)
TO li_memory_api;
REVOKE ALL PRIVILEGES ON li_runtime_data.portfolio_holdings
FROM PUBLIC, anon, authenticated, service_role, li_backend_runtime, li_memory_api,
  li_memory_theo, li_memory_owner_confirmation, li_artifact_retention,
  li_retention_runtime;

DO $$
DECLARE
  v_role TEXT;
  function_name TEXT;
  role_name NAME := (SELECT migration_role FROM migration_042_authority_state);
BEGIN
  IF (SELECT added_create FROM migration_042_authority_state) THEN
    EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner';
  END IF;
  IF (SELECT added_owner FROM migration_042_authority_state) THEN
    EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I', role_name);
  END IF;
  FOREACH function_name IN ARRAY ARRAY[
    'li_api.list_portfolio_holdings(text)',
    'li_api.upsert_portfolio_holding(uuid,text,text,text,numeric,numeric,text,numeric,text)',
    'li_api.archive_portfolio_holding(uuid)'
  ] LOOP
    IF (SELECT pg_get_userbyid(proowner) FROM pg_proc
        WHERE oid = function_name::REGPROCEDURE)
      IS DISTINCT FROM 'li_memory_function_owner' THEN
      RAISE EXCEPTION 'Function % has unexpected owner', function_name;
    END IF;
  END LOOP;
  IF NOT has_function_privilege('li_backend_runtime',
      'li_api.list_portfolio_holdings(text)', 'EXECUTE')
    OR NOT has_function_privilege('li_backend_runtime',
      'li_api.upsert_portfolio_holding(uuid,text,text,text,numeric,numeric,text,numeric,text)',
      'EXECUTE')
    OR NOT has_function_privilege('li_backend_runtime',
      'li_api.archive_portfolio_holding(uuid)', 'EXECUTE') THEN
    RAISE EXCEPTION 'Backend runtime lost required portfolio execution';
  END IF;
  FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role',
    'li_memory_theo', 'li_memory_owner_confirmation', 'li_artifact_retention',
    'li_retention_runtime'] LOOP
    IF has_function_privilege(v_role,
        'li_api.list_portfolio_holdings(text)', 'EXECUTE')
      OR has_function_privilege(v_role,
        'li_api.upsert_portfolio_holding(uuid,text,text,text,numeric,numeric,text,numeric,text)',
        'EXECUTE')
      OR has_table_privilege(v_role,
        'li_runtime_data.portfolio_holdings', 'SELECT') THEN
      RAISE EXCEPTION 'Portfolio authority exceeds Li runtime for %', v_role;
    END IF;
  END LOOP;
  IF has_table_privilege('li_backend_runtime',
      'li_runtime_data.portfolio_holdings', 'SELECT') THEN
    RAISE EXCEPTION 'Backend retained direct portfolio table access';
  END IF;
  IF (SELECT added_create FROM migration_042_authority_state)
    AND has_schema_privilege('li_memory_function_owner', 'li_api', 'CREATE') THEN
    RAISE EXCEPTION 'Temporary schema authority was not removed';
  END IF;
  IF (SELECT added_owner FROM migration_042_authority_state)
    AND (pg_has_role(role_name, 'li_memory_function_owner', 'SET')
      OR pg_has_role(role_name, 'li_memory_function_owner', 'USAGE')) THEN
    RAISE EXCEPTION 'Temporary function-owner authority was not removed';
  END IF;
END $$;

INSERT INTO li_memory.schema_versions(version, description)
VALUES ('0.42', 'Private owner-entered portfolio workspace without trading authority');
COMMIT;
