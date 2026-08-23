
BEGIN;


-- ============================================================
-- Li OS Memory Database Schema
-- Version: 0.1
-- Primary User: Christoffer Melldén
-- Memory Curator: Theo
-- Security Guardian: Heimdall
--
-- Purpose:
-- Define the initial PostgreSQL-compatible canonical memory
-- structure for Li OS.
--
-- IMPORTANT:
-- This file defines HOW personal memory is stored.
-- It must not contain Christoffer's actual sensitive memory.
-- ============================================================


-- ============================================================
-- 1. EXTENSIONS
-- ============================================================

-- Provides gen_random_uuid().
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
-- 2. SCHEMA VERSION
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_versions (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_versions (
    version,
    description
)
VALUES (
    '0.1',
    'Initial Li OS canonical personal memory schema'
)
ON CONFLICT (version) DO NOTHING;


-- ============================================================
-- 3. USERS
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_key TEXT NOT NULL UNIQUE,

    full_name TEXT NOT NULL,
    display_name TEXT,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (
            status IN (
                'active',
                'future_not_active',
                'inactive',
                'archived'
            )
        ),

    role TEXT NOT NULL DEFAULT 'primary_user'
        CHECK (
            role IN (
                'owner',
                'primary_user',
                'secondary_user'
            )
        ),

    memory_namespace TEXT NOT NULL UNIQUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);


-- ============================================================
-- 4. PEOPLE
-- ============================================================

-- People who are meaningful within a user's personal context.
--
-- These are not Li OS users unless separately represented
-- in the users table.

CREATE TABLE IF NOT EXISTS people (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    person_key TEXT,

    full_name TEXT NOT NULL,
    display_name TEXT,

    relationship_type TEXT,

    sensitivity TEXT NOT NULL DEFAULT 'personal'
        CHECK (
            sensitivity IN (
                'low',
                'personal',
                'sensitive',
                'highly_sensitive'
            )
        ),

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE (owner_user_id, person_key)
);


-- ============================================================
-- 5. CANONICAL MEMORY RECORDS
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    memory_key TEXT,

    memory_class TEXT NOT NULL
        CHECK (
            memory_class IN (
                'explicit_fact',
                'explicit_preference',
                'explicit_opinion',
                'observation',
                'inference',
                'historical_fact',
                'outcome',
                'commitment',
                'open_loop',
                'temporary_context'
            )
        ),

    domain TEXT NOT NULL,

    title TEXT,

    value_text TEXT,
    value_json JSONB,

    source_type TEXT NOT NULL
        CHECK (
            source_type IN (
                'user_explicit',
                'connected_source',
                'document',
                'agent_observation',
                'agent_inference',
                'import',
                'system',
                'unknown'
            )
        ),

    source_user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    source_agent TEXT,

    source_reference TEXT,

    confidence NUMERIC(4,3) NOT NULL DEFAULT 1.000
        CHECK (
            confidence >= 0
            AND confidence <= 1
        ),

    truth_status TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (
            truth_status IN (
                'confirmed',
                'likely',
                'inferred',
                'disputed',
                'outdated',
                'unknown'
            )
        ),

    temporal_status TEXT NOT NULL DEFAULT 'current'
        CHECK (
            temporal_status IN (
                'current',
                'historical',
                'planned',
                'temporary',
                'unresolved'
            )
        ),

    sensitivity TEXT NOT NULL DEFAULT 'personal'
        CHECK (
            sensitivity IN (
                'low',
                'personal',
                'sensitive',
                'highly_sensitive'
            )
        ),

    private_to_li BOOLEAN NOT NULL DEFAULT FALSE,

    confirmed_by_user BOOLEAN NOT NULL DEFAULT FALSE,

    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,

    review_after TIMESTAMPTZ,

    supersedes_memory_id UUID
        REFERENCES memory_records(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    deleted_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    CHECK (
        value_text IS NOT NULL
        OR value_json IS NOT NULL
    ),

    CHECK (
        valid_until IS NULL
        OR valid_from IS NULL
        OR valid_until >= valid_from
    ),

    UNIQUE (owner_user_id, memory_key)
);


-- ============================================================
-- 6. MEMORY RELATIONSHIPS
-- ============================================================

-- Allows memories to support, contradict, supersede,
-- explain, or otherwise relate to other memories.

CREATE TABLE IF NOT EXISTS memory_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    source_memory_id UUID NOT NULL
        REFERENCES memory_records(id)
        ON DELETE CASCADE,

    target_memory_id UUID NOT NULL
        REFERENCES memory_records(id)
        ON DELETE CASCADE,

    relation_type TEXT NOT NULL
        CHECK (
            relation_type IN (
                'supports',
                'contradicts',
                'related_to',
                'derived_from',
                'supersedes',
                'caused_by',
                'resulted_in',
                'evidence_for',
                'evidence_against'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    CHECK (source_memory_id <> target_memory_id),

    UNIQUE (
        source_memory_id,
        target_memory_id,
        relation_type
    )
);


-- ============================================================
-- 7. MEMORY ↔ PEOPLE LINKS
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_person_links (
    memory_id UUID NOT NULL
        REFERENCES memory_records(id)
        ON DELETE CASCADE,

    person_id UUID NOT NULL
        REFERENCES people(id)
        ON DELETE CASCADE,

    relationship_to_memory TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        memory_id,
        person_id
    )
);


-- ============================================================
-- 8. GOALS
-- ============================================================

CREATE TABLE IF NOT EXISTS goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    goal_key TEXT,

    title TEXT NOT NULL,
    description TEXT,

    domain TEXT,

    status TEXT NOT NULL DEFAULT 'idea'
        CHECK (
            status IN (
                'idea',
                'active',
                'paused',
                'achieved',
                'abandoned',
                'superseded'
            )
        ),

    importance INTEGER
        CHECK (
            importance IS NULL
            OR (
                importance >= 1
                AND importance <= 5
            )
        ),

    target_date DATE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    sensitivity TEXT NOT NULL DEFAULT 'personal'
        CHECK (
            sensitivity IN (
                'low',
                'personal',
                'sensitive',
                'highly_sensitive'
            )
        ),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE (owner_user_id, goal_key)
);


-- ============================================================
-- 9. DECISIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    decision_key TEXT,

    title TEXT NOT NULL,
    description TEXT,

    domain TEXT,

    decision_status TEXT NOT NULL DEFAULT 'considering'
        CHECK (
            decision_status IN (
                'considering',
                'decided',
                'implemented',
                'reversed',
                'superseded'
            )
        ),

    chosen_option TEXT,

    rationale TEXT,

    decided_at TIMESTAMPTZ,

    outcome TEXT,

    outcome_rating INTEGER
        CHECK (
            outcome_rating IS NULL
            OR (
                outcome_rating >= 1
                AND outcome_rating <= 5
            )
        ),

    reviewed_at TIMESTAMPTZ,

    sensitivity TEXT NOT NULL DEFAULT 'personal'
        CHECK (
            sensitivity IN (
                'low',
                'personal',
                'sensitive',
                'highly_sensitive'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE (owner_user_id, decision_key)
);


-- ============================================================
-- 10. COMMITMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS commitments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    commitment_key TEXT,

    title TEXT NOT NULL,
    description TEXT,

    domain TEXT,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (
            status IN (
                'active',
                'completed',
                'cancelled',
                'missed',
                'superseded'
            )
        ),

    due_at TIMESTAMPTZ,

    related_person_id UUID
        REFERENCES people(id)
        ON DELETE SET NULL,

    source_memory_id UUID
        REFERENCES memory_records(id)
        ON DELETE SET NULL,

    importance INTEGER
        CHECK (
            importance IS NULL
            OR (
                importance >= 1
                AND importance <= 5
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE (owner_user_id, commitment_key)
);


-- ============================================================
-- 11. OPEN LOOPS
-- ============================================================

CREATE TABLE IF NOT EXISTS open_loops (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    open_loop_key TEXT,

    title TEXT NOT NULL,
    description TEXT,

    loop_type TEXT
        CHECK (
            loop_type IS NULL
            OR loop_type IN (
                'awaiting_reply',
                'follow_up',
                'unresolved_decision',
                'pending_booking',
                'document_to_send',
                'question_to_revisit',
                'other'
            )
        ),

    status TEXT NOT NULL DEFAULT 'open'
        CHECK (
            status IN (
                'open',
                'waiting',
                'resolved',
                'cancelled',
                'superseded'
            )
        ),

    due_at TIMESTAMPTZ,
    follow_up_at TIMESTAMPTZ,

    related_person_id UUID
        REFERENCES people(id)
        ON DELETE SET NULL,

    source_memory_id UUID
        REFERENCES memory_records(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    resolved_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE (owner_user_id, open_loop_key)
);


-- ============================================================
-- 12. TIMELINE EVENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS timeline_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    event_key TEXT,

    title TEXT NOT NULL,
    description TEXT,

    domain TEXT,

    event_type TEXT,

    occurred_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,

    location_text TEXT,

    sensitivity TEXT NOT NULL DEFAULT 'personal'
        CHECK (
            sensitivity IN (
                'low',
                'personal',
                'sensitive',
                'highly_sensitive'
            )
        ),

    source_memory_id UUID
        REFERENCES memory_records(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    CHECK (
        ended_at IS NULL
        OR started_at IS NULL
        OR ended_at >= started_at
    ),

    UNIQUE (owner_user_id, event_key)
);


-- ============================================================
-- 13. DOCUMENTS
-- ============================================================

-- Stores metadata and secure-storage references only.
--
-- Actual sensitive document contents should live in protected
-- file/object storage rather than directly in this table.

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    document_key TEXT,

    title TEXT NOT NULL,

    document_type TEXT,

    storage_provider TEXT,
    storage_reference TEXT,

    mime_type TEXT,

    source_type TEXT,
    source_reference TEXT,

    sensitivity TEXT NOT NULL DEFAULT 'sensitive'
        CHECK (
            sensitivity IN (
                'low',
                'personal',
                'sensitive',
                'highly_sensitive'
            )
        ),

    encrypted BOOLEAN NOT NULL DEFAULT TRUE,

    content_hash TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE (owner_user_id, document_key)
);


-- ============================================================
-- 14. MEMORY ↔ DOCUMENT LINKS
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_document_links (
    memory_id UUID NOT NULL
        REFERENCES memory_records(id)
        ON DELETE CASCADE,

    document_id UUID NOT NULL
        REFERENCES documents(id)
        ON DELETE CASCADE,

    link_type TEXT NOT NULL DEFAULT 'source'
        CHECK (
            link_type IN (
                'source',
                'evidence',
                'related'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        memory_id,
        document_id,
        link_type
    )
);


-- ============================================================
-- 15. MEMORY WRITE PROPOSALS
-- ============================================================

-- Specialists should normally propose memory changes rather
-- than directly writing canonical memory.

CREATE TABLE IF NOT EXISTS memory_write_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    proposed_by_agent TEXT NOT NULL,

    proposed_class TEXT NOT NULL,

    proposed_domain TEXT NOT NULL,

    proposed_value_text TEXT,
    proposed_value_json JSONB,

    proposed_truth_status TEXT,

    proposed_temporal_status TEXT,

    proposed_sensitivity TEXT,

    reason TEXT,

    source_reference TEXT,

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'approved',
                'rejected',
                'merged',
                'needs_user_confirmation'
            )
        ),

    reviewed_by_agent TEXT,

    reviewed_at TIMESTAMPTZ,

    resulting_memory_id UUID
        REFERENCES memory_records(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    CHECK (
        proposed_value_text IS NOT NULL
        OR proposed_value_json IS NOT NULL
    )
);


-- ============================================================
-- 16. AGENT MEMORY ACCESS GRANTS
-- ============================================================

-- Supports temporary or explicit agent access beyond normal
-- configuration permissions.
--
-- Permanent baseline permissions remain governed by:
-- memory/permissions.yaml

CREATE TABLE IF NOT EXISTS memory_access_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    agent_id TEXT NOT NULL,

    domain TEXT,

    memory_id UUID
        REFERENCES memory_records(id)
        ON DELETE CASCADE,

    access_level TEXT NOT NULL
        CHECK (
            access_level IN (
                'task_specific',
                'summary',
                'restricted',
                'broad',
                'administrative'
            )
        ),

    purpose TEXT NOT NULL,

    temporary BOOLEAN NOT NULL DEFAULT TRUE,

    granted_by TEXT NOT NULL,

    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ,

    revoked_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    CHECK (
        temporary = FALSE
        OR expires_at IS NOT NULL
    )
);


-- ============================================================
-- 17. MEMORY AUDIT LOG
-- ============================================================

-- Audit metadata should avoid duplicating sensitive content.

CREATE TABLE IF NOT EXISTS memory_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    actor_type TEXT NOT NULL
        CHECK (
            actor_type IN (
                'user',
                'agent',
                'system',
                'tool',
                'administrator'
            )
        ),

    actor_id TEXT NOT NULL,

    action TEXT NOT NULL,

    resource_type TEXT NOT NULL,

    resource_id UUID,

    purpose TEXT,

    permission_basis TEXT,

    sensitivity TEXT,

    success BOOLEAN NOT NULL DEFAULT TRUE,

    error_code TEXT,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);


-- ============================================================
-- 18. OUTCOME / EXPERIENCE RECORDS
-- ============================================================

CREATE TABLE IF NOT EXISTS experience_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    experience_key TEXT,

    domain TEXT NOT NULL,

    title TEXT NOT NULL,

    recommendation TEXT,

    action_taken TEXT,

    outcome TEXT,

    outcome_rating INTEGER
        CHECK (
            outcome_rating IS NULL
            OR (
                outcome_rating >= 1
                AND outcome_rating <= 5
            )
        ),

    lesson TEXT,

    confidence NUMERIC(4,3)
        CHECK (
            confidence IS NULL
            OR (
                confidence >= 0
                AND confidence <= 1
            )
        ),

    related_decision_id UUID
        REFERENCES decisions(id)
        ON DELETE SET NULL,

    source_memory_id UUID
        REFERENCES memory_records(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE (owner_user_id, experience_key)
);


-- ============================================================
-- 19. TAGS
-- ============================================================

CREATE TABLE IF NOT EXISTS tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    name TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (owner_user_id, name)
);


CREATE TABLE IF NOT EXISTS memory_tags (
    memory_id UUID NOT NULL
        REFERENCES memory_records(id)
        ON DELETE CASCADE,

    tag_id UUID NOT NULL
        REFERENCES tags(id)
        ON DELETE CASCADE,

    PRIMARY KEY (
        memory_id,
        tag_id
    )
);


-- ============================================================
-- 20. UPDATED_AT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


DROP TRIGGER IF EXISTS users_set_updated_at
ON users;

CREATE TRIGGER users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS people_set_updated_at
ON people;

CREATE TRIGGER people_set_updated_at
BEFORE UPDATE ON people
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS memory_records_set_updated_at
ON memory_records;

CREATE TRIGGER memory_records_set_updated_at
BEFORE UPDATE ON memory_records
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS goals_set_updated_at
ON goals;

CREATE TRIGGER goals_set_updated_at
BEFORE UPDATE ON goals
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS decisions_set_updated_at
ON decisions;

CREATE TRIGGER decisions_set_updated_at
BEFORE UPDATE ON decisions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS commitments_set_updated_at
ON commitments;

CREATE TRIGGER commitments_set_updated_at
BEFORE UPDATE ON commitments
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS open_loops_set_updated_at
ON open_loops;

CREATE TRIGGER open_loops_set_updated_at
BEFORE UPDATE ON open_loops
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS timeline_events_set_updated_at
ON timeline_events;

CREATE TRIGGER timeline_events_set_updated_at
BEFORE UPDATE ON timeline_events
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS documents_set_updated_at
ON documents;

CREATE TRIGGER documents_set_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


-- ============================================================
-- 21. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_memory_owner
    ON memory_records(owner_user_id);


CREATE INDEX IF NOT EXISTS idx_memory_domain
    ON memory_records(owner_user_id, domain);


CREATE INDEX IF NOT EXISTS idx_memory_class
    ON memory_records(owner_user_id, memory_class);


CREATE INDEX IF NOT EXISTS idx_memory_truth
    ON memory_records(owner_user_id, truth_status);


CREATE INDEX IF NOT EXISTS idx_memory_temporal
    ON memory_records(owner_user_id, temporal_status);


CREATE INDEX IF NOT EXISTS idx_memory_sensitivity
    ON memory_records(owner_user_id, sensitivity);


CREATE INDEX IF NOT EXISTS idx_memory_review_after
    ON memory_records(review_after)
    WHERE review_after IS NOT NULL;


CREATE INDEX IF NOT EXISTS idx_memory_active
    ON memory_records(owner_user_id, created_at DESC)
    WHERE deleted_at IS NULL;


CREATE INDEX IF NOT EXISTS idx_people_owner
    ON people(owner_user_id);


CREATE INDEX IF NOT EXISTS idx_goals_status
    ON goals(owner_user_id, status);


CREATE INDEX IF NOT EXISTS idx_commitments_status_due
    ON commitments(owner_user_id, status, due_at);


CREATE INDEX IF NOT EXISTS idx_open_loops_status_followup
    ON open_loops(owner_user_id, status, follow_up_at);


CREATE INDEX IF NOT EXISTS idx_timeline_owner_date
    ON timeline_events(owner_user_id, occurred_at DESC);


CREATE INDEX IF NOT EXISTS idx_memory_proposals_status
    ON memory_write_proposals(owner_user_id, status);


CREATE INDEX IF NOT EXISTS idx_access_grants_agent
    ON memory_access_grants(agent_id, expires_at);


CREATE INDEX IF NOT EXISTS idx_audit_owner_time
    ON memory_audit_log(owner_user_id, occurred_at DESC);


CREATE INDEX IF NOT EXISTS idx_experience_owner_domain
    ON experience_records(owner_user_id, domain);


-- ============================================================
-- 22. FULL-TEXT SEARCH INDEX
-- ============================================================

-- Initial native PostgreSQL search.
--
-- Semantic/vector retrieval can be added later as a derived
-- search layer without changing the canonical records.

CREATE INDEX IF NOT EXISTS idx_memory_text_search
ON memory_records
USING GIN (
    to_tsvector(
        'simple',
        COALESCE(title, '')
        || ' '
        || COALESCE(value_text, '')
    )
);


-- ============================================================
-- 23. INITIAL USER RECORD
-- ============================================================

-- This is intentionally minimal and non-sensitive.
-- Detailed personal memory belongs in memory_records and the
-- protected memory system, not in GitHub source code.

INSERT INTO users (
    user_key,
    full_name,
    display_name,
    status,
    role,
    memory_namespace
)
VALUES (
    'christoffer',
    'Christoffer Melldén',
    'Christoffer',
    'active',
    'primary_user',
    'user/christoffer'
)
ON CONFLICT (user_key) DO NOTHING;


-- ============================================================
-- 24. SECURITY NOTE
-- ============================================================

-- Row-level security, database roles, API authentication,
-- encryption-key handling, network access rules, and secret
-- management should be implemented as infrastructure rather
-- than assumed from this schema alone.
--
-- Agents should eventually access these tables through the
-- controlled Li OS Memory API rather than unrestricted direct
-- database credentials.


-- ============================================================
-- 25. SEMANTIC SEARCH NOTE
-- ============================================================

-- Semantic/vector search is intentionally NOT part of the
-- canonical v0.1 schema.
--
-- When implemented, embeddings should be:
--
--   1. derived from canonical memory;
--   2. rebuildable;
--   3. protected according to source sensitivity;
--   4. never treated as the source of truth.
--
-- A future migration may add pgvector or another semantic
-- retrieval technology after Ada, Theo, and Heimdall evaluate
-- the implementation.


-- ============================================================
-- 26. FINAL PRINCIPLE
-- ============================================================

-- GitHub defines the structure.
--
-- PostgreSQL stores canonical personal memory.
--
-- Theo protects memory quality.
--
-- Heimdall protects access.
--
-- Li retrieves only what is relevant.
--
-- Models, embeddings, caches, summaries, and tools may change.
--
-- Christoffer's accumulated personal history must remain
-- portable and recoverable.

COMMIT;
