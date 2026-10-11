-- IPF Process Modeling Engine - SQLite Schema V1
-- Logical/physical schema consolidated 2026-10-03
-- Core ontology: ENTITY / RELATION / RULE
-- SQLite responsibilities: persistence + structural integrity.
-- Domain layer responsibilities are documented at the end of this file.

PRAGMA foreign_keys = ON;

BEGIN;

-- ============================================================
-- 1. WORKSPACE
-- ============================================================
CREATE TABLE workspace (
    id              INTEGER PRIMARY KEY,
    uid             TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    created_at      TEXT NOT NULL
);

-- ============================================================
-- 2. CORE / CUSTOM CATALOGS
-- workspace_id NULL = system/core catalog entry.
-- workspace_id set  = workspace-specific custom entry.
-- ============================================================
CREATE TABLE entity_type (
    id              INTEGER PRIMARY KEY,
    uid             TEXT NOT NULL UNIQUE,
    workspace_id    INTEGER REFERENCES workspace(id) ON DELETE RESTRICT,
    parent_type_id  INTEGER REFERENCES entity_type(id) ON DELETE RESTRICT,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    is_core         INTEGER NOT NULL DEFAULT 0 CHECK (is_core IN (0,1)),
    CHECK ((is_core = 1 AND workspace_id IS NULL) OR is_core = 0)
);

CREATE UNIQUE INDEX uq_entity_type_core_code
    ON entity_type(code)
    WHERE workspace_id IS NULL;
CREATE UNIQUE INDEX uq_entity_type_workspace_code
    ON entity_type(workspace_id, code)
    WHERE workspace_id IS NOT NULL;

CREATE TABLE relation_semantic (
    id              INTEGER PRIMARY KEY,
    uid             TEXT NOT NULL UNIQUE,
    workspace_id    INTEGER REFERENCES workspace(id) ON DELETE RESTRICT,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    inverse_label   TEXT,
    is_core         INTEGER NOT NULL DEFAULT 0 CHECK (is_core IN (0,1)),
    is_symmetric    INTEGER NOT NULL DEFAULT 0 CHECK (is_symmetric IN (0,1)),
    is_acyclic      INTEGER NOT NULL DEFAULT 0 CHECK (is_acyclic IN (0,1)),
    CHECK ((is_core = 1 AND workspace_id IS NULL) OR is_core = 0)
);

CREATE UNIQUE INDEX uq_relation_semantic_core_code
    ON relation_semantic(code)
    WHERE workspace_id IS NULL;
CREATE UNIQUE INDEX uq_relation_semantic_workspace_code
    ON relation_semantic(workspace_id, code)
    WHERE workspace_id IS NOT NULL;

CREATE TABLE relation_signature (
    id                      INTEGER PRIMARY KEY,
    relation_semantic_id    INTEGER NOT NULL REFERENCES relation_semantic(id) ON DELETE CASCADE,
    source_entity_type_id   INTEGER NOT NULL REFERENCES entity_type(id) ON DELETE RESTRICT,
    target_entity_type_id   INTEGER NOT NULL REFERENCES entity_type(id) ON DELETE RESTRICT,
    UNIQUE (relation_semantic_id, source_entity_type_id, target_entity_type_id)
);

CREATE TABLE property_definition (
    id              INTEGER PRIMARY KEY,
    uid             TEXT NOT NULL UNIQUE,
    workspace_id    INTEGER REFERENCES workspace(id) ON DELETE RESTRICT,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    value_type      TEXT NOT NULL CHECK (value_type IN (
                        'BOOLEAN','INTEGER','NUMBER','TEXT',
                        'DATE','DATETIME','DURATION','ENUM'
                    )),
    unit            TEXT,
    scope           TEXT NOT NULL CHECK (scope IN ('DEFINITION','INSTANCE','BOTH')),
    track_history   INTEGER NOT NULL DEFAULT 0 CHECK (track_history IN (0,1)),
    is_core         INTEGER NOT NULL DEFAULT 0 CHECK (is_core IN (0,1)),
    CHECK ((is_core = 1 AND workspace_id IS NULL) OR is_core = 0)
);

CREATE UNIQUE INDEX uq_property_definition_core_code
    ON property_definition(code)
    WHERE workspace_id IS NULL;
CREATE UNIQUE INDEX uq_property_definition_workspace_code
    ON property_definition(workspace_id, code)
    WHERE workspace_id IS NOT NULL;

CREATE TABLE property_applicability (
    property_definition_id  INTEGER NOT NULL REFERENCES property_definition(id) ON DELETE CASCADE,
    entity_type_id          INTEGER NOT NULL REFERENCES entity_type(id) ON DELETE CASCADE,
    PRIMARY KEY (property_definition_id, entity_type_id)
);

-- Engine capability catalog. Implementations live in Python/domain code.
CREATE TABLE operation_definition (
    code            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    min_args        INTEGER NOT NULL CHECK (min_args >= 0),
    max_args        INTEGER CHECK (max_args IS NULL OR max_args >= min_args)
);

-- ============================================================
-- 3. ENTITY: stable identity -> immutable definitions
-- ============================================================
CREATE TABLE entity_identity (
    id              INTEGER PRIMARY KEY,
    uid             TEXT NOT NULL UNIQUE,
    workspace_id    INTEGER NOT NULL REFERENCES workspace(id) ON DELETE RESTRICT,
    entity_type_id  INTEGER NOT NULL REFERENCES entity_type(id) ON DELETE RESTRICT,
    stable_code     TEXT,
    created_at      TEXT NOT NULL,
    retired_at      TEXT
);

CREATE UNIQUE INDEX uq_entity_identity_workspace_stable_code
    ON entity_identity(workspace_id, stable_code)
    WHERE stable_code IS NOT NULL;
CREATE INDEX ix_entity_identity_workspace ON entity_identity(workspace_id);
CREATE INDEX ix_entity_identity_type ON entity_identity(entity_type_id);

CREATE TABLE entity_definition (
    id                  INTEGER PRIMARY KEY,
    uid                 TEXT NOT NULL UNIQUE,
    entity_identity_id  INTEGER NOT NULL REFERENCES entity_identity(id) ON DELETE RESTRICT,
    name                TEXT NOT NULL,
    description         TEXT,
    origin              TEXT NOT NULL DEFAULT 'MODELED'
                        CHECK (origin IN ('MODELED','OBSERVED_AD_HOC','IMPORTED','DISCOVERED')),
    created_at          TEXT NOT NULL
);

CREATE INDEX ix_entity_definition_identity ON entity_definition(entity_identity_id);

-- ============================================================
-- 4. RELATION: simple domain relations connect Entity Identities.
-- Complex/n-ary relations are reified as entities.
-- ============================================================
CREATE TABLE relation_definition (
    id                          INTEGER PRIMARY KEY,
    uid                         TEXT NOT NULL UNIQUE,
    workspace_id                INTEGER NOT NULL REFERENCES workspace(id) ON DELETE RESTRICT,
    semantic_id                 INTEGER NOT NULL REFERENCES relation_semantic(id) ON DELETE RESTRICT,
    source_entity_identity_id   INTEGER NOT NULL REFERENCES entity_identity(id) ON DELETE RESTRICT,
    target_entity_identity_id   INTEGER NOT NULL REFERENCES entity_identity(id) ON DELETE RESTRICT,
    created_at                  TEXT NOT NULL
);

CREATE INDEX ix_relation_definition_workspace ON relation_definition(workspace_id);
CREATE INDEX ix_relation_definition_semantic ON relation_definition(semantic_id);
CREATE INDEX ix_relation_definition_source ON relation_definition(source_entity_identity_id);
CREATE INDEX ix_relation_definition_target ON relation_definition(target_entity_identity_id);
CREATE INDEX ix_relation_definition_triple
    ON relation_definition(source_entity_identity_id, semantic_id, target_entity_identity_id);

-- ============================================================
-- 5. PROPERTY VALUES FOR DEFINITIONS
-- Exactly one typed value column should be populated; compatibility
-- with property_definition.value_type is validated by the domain layer.
-- ============================================================
CREATE TABLE definition_property_value (
    entity_definition_id       INTEGER NOT NULL REFERENCES entity_definition(id) ON DELETE CASCADE,
    property_definition_id     INTEGER NOT NULL REFERENCES property_definition(id) ON DELETE RESTRICT,
    value_text                 TEXT,
    value_integer              INTEGER,
    value_real                 REAL,
    value_boolean              INTEGER CHECK (value_boolean IS NULL OR value_boolean IN (0,1)),
    PRIMARY KEY (entity_definition_id, property_definition_id),
    CHECK (
        (value_text IS NOT NULL) +
        (value_integer IS NOT NULL) +
        (value_real IS NOT NULL) +
        (value_boolean IS NOT NULL) = 1
    )
);

CREATE TABLE relation_definition_property_value (
    relation_definition_id     INTEGER NOT NULL REFERENCES relation_definition(id) ON DELETE CASCADE,
    property_definition_id     INTEGER NOT NULL REFERENCES property_definition(id) ON DELETE RESTRICT,
    value_text                 TEXT,
    value_integer              INTEGER,
    value_real                 REAL,
    value_boolean              INTEGER CHECK (value_boolean IS NULL OR value_boolean IN (0,1)),
    PRIMARY KEY (relation_definition_id, property_definition_id),
    CHECK (
        (value_text IS NOT NULL) +
        (value_integer IS NOT NULL) +
        (value_real IS NOT NULL) +
        (value_boolean IS NOT NULL) = 1
    )
);

-- ============================================================
-- 6. EXPRESSION LANGUAGE
-- Each expression is an owned tree (not a shared DAG in V1).
-- Exactly one root node (parent_node_id IS NULL) is required by
-- domain validation before publication.
-- ============================================================
CREATE TABLE expression (
    id              INTEGER PRIMARY KEY,
    uid             TEXT NOT NULL UNIQUE,
    created_at      TEXT NOT NULL
);

CREATE TABLE expression_node (
    id                      INTEGER PRIMARY KEY,
    expression_id           INTEGER NOT NULL REFERENCES expression(id) ON DELETE CASCADE,
    parent_node_id          INTEGER REFERENCES expression_node(id) ON DELETE CASCADE,
    position                INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0),
    node_kind               TEXT NOT NULL CHECK (node_kind IN ('LITERAL','REFERENCE','OPERATION')),

    operation_code          TEXT REFERENCES operation_definition(code) ON DELETE RESTRICT,

    literal_type            TEXT CHECK (literal_type IS NULL OR literal_type IN (
                                'BOOLEAN','INTEGER','NUMBER','TEXT',
                                'DATE','DATETIME','DURATION','ENUM'
                            )),
    literal_text            TEXT,
    literal_integer         INTEGER,
    literal_real            REAL,
    literal_boolean         INTEGER CHECK (literal_boolean IS NULL OR literal_boolean IN (0,1)),

    reference_kind          TEXT CHECK (reference_kind IS NULL OR reference_kind IN (
                                'ENTITY','PROPERTY','VARIABLE','CONTEXT'
                            )),
    entity_identity_id      INTEGER REFERENCES entity_identity(id) ON DELETE RESTRICT,
    property_definition_id  INTEGER REFERENCES property_definition(id) ON DELETE RESTRICT,
    variable_name           TEXT,
    reference_scope         TEXT CHECK (reference_scope IS NULL OR reference_scope IN (
                                'DEFINITION','INSTANCE','CONTEXT'
                            )),

    CHECK (
        (node_kind = 'OPERATION' AND operation_code IS NOT NULL AND literal_type IS NULL AND reference_kind IS NULL)
        OR
        (node_kind = 'REFERENCE' AND operation_code IS NULL AND literal_type IS NULL AND reference_kind IS NOT NULL)
        OR
        (node_kind = 'LITERAL' AND operation_code IS NULL AND literal_type IS NOT NULL AND reference_kind IS NULL)
    ),

    CHECK (
        node_kind <> 'LITERAL'
        OR (
            (literal_text IS NOT NULL) +
            (literal_integer IS NOT NULL) +
            (literal_real IS NOT NULL) +
            (literal_boolean IS NOT NULL) = 1
        )
    )
);

CREATE INDEX ix_expression_node_expression
    ON expression_node(expression_id, parent_node_id, position);
CREATE INDEX ix_expression_node_parent ON expression_node(parent_node_id);
CREATE INDEX ix_expression_node_entity_reference ON expression_node(entity_identity_id);
CREATE INDEX ix_expression_node_property_reference ON expression_node(property_definition_id);

-- ============================================================
-- 7. RULE: stable identity -> immutable definitions
-- ============================================================
CREATE TABLE rule_identity (
    id              INTEGER PRIMARY KEY,
    uid             TEXT NOT NULL UNIQUE,
    workspace_id    INTEGER NOT NULL REFERENCES workspace(id) ON DELETE RESTRICT,
    stable_code     TEXT,
    created_at      TEXT NOT NULL,
    retired_at      TEXT
);

CREATE UNIQUE INDEX uq_rule_identity_workspace_stable_code
    ON rule_identity(workspace_id, stable_code)
    WHERE stable_code IS NOT NULL;

CREATE TABLE rule_definition (
    id                              INTEGER PRIMARY KEY,
    uid                             TEXT NOT NULL UNIQUE,
    rule_identity_id                INTEGER NOT NULL REFERENCES rule_identity(id) ON DELETE RESTRICT,
    semantic                        TEXT NOT NULL CHECK (semantic IN ('ASSERTION','DERIVATION')),
    name                            TEXT NOT NULL,
    description                     TEXT,
    applicability_expression_id     INTEGER REFERENCES expression(id) ON DELETE RESTRICT,
    body_expression_id              INTEGER NOT NULL REFERENCES expression(id) ON DELETE RESTRICT,
    target_entity_identity_id       INTEGER REFERENCES entity_identity(id) ON DELETE RESTRICT,
    target_property_definition_id   INTEGER REFERENCES property_definition(id) ON DELETE RESTRICT,
    severity                        TEXT,
    created_at                      TEXT NOT NULL,
    CHECK (
        (semantic = 'ASSERTION'
            AND target_entity_identity_id IS NULL
            AND target_property_definition_id IS NULL)
        OR
        (semantic = 'DERIVATION'
            AND target_entity_identity_id IS NOT NULL
            AND target_property_definition_id IS NOT NULL)
    )
);

CREATE INDEX ix_rule_definition_identity ON rule_definition(rule_identity_id);
CREATE INDEX ix_rule_definition_body_expression ON rule_definition(body_expression_id);

-- ============================================================
-- 8. PROCESS MODELS / IMMUTABLE PUBLISHED REVISIONS
-- ============================================================
CREATE TABLE process_model (
    id              INTEGER PRIMARY KEY,
    uid             TEXT NOT NULL UNIQUE,
    workspace_id    INTEGER NOT NULL REFERENCES workspace(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,
    description     TEXT,
    created_at      TEXT NOT NULL,
    retired_at      TEXT
);

CREATE INDEX ix_process_model_workspace ON process_model(workspace_id);

CREATE TABLE model_revision (
    id                  INTEGER PRIMARY KEY,
    uid                 TEXT NOT NULL UNIQUE,
    process_model_id    INTEGER NOT NULL REFERENCES process_model(id) ON DELETE RESTRICT,
    parent_revision_id  INTEGER REFERENCES model_revision(id) ON DELETE RESTRICT,
    revision_code       TEXT NOT NULL,
    purpose             TEXT,
    status              TEXT NOT NULL DEFAULT 'DRAFT'
                        CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED')),
    created_at          TEXT NOT NULL,
    published_at        TEXT,
    UNIQUE (process_model_id, revision_code),
    CHECK (
        (status = 'PUBLISHED' AND published_at IS NOT NULL)
        OR status <> 'PUBLISHED'
    )
);

CREATE INDEX ix_model_revision_model ON model_revision(process_model_id);
CREATE INDEX ix_model_revision_parent ON model_revision(parent_revision_id);

CREATE TABLE model_revision_entity (
    model_revision_id      INTEGER NOT NULL REFERENCES model_revision(id) ON DELETE CASCADE,
    entity_definition_id   INTEGER NOT NULL REFERENCES entity_definition(id) ON DELETE RESTRICT,
    PRIMARY KEY (model_revision_id, entity_definition_id)
);

CREATE INDEX ix_model_revision_entity_revision ON model_revision_entity(model_revision_id);
CREATE INDEX ix_model_revision_entity_definition ON model_revision_entity(entity_definition_id);

CREATE TABLE model_revision_relation (
    model_revision_id       INTEGER NOT NULL REFERENCES model_revision(id) ON DELETE CASCADE,
    relation_definition_id  INTEGER NOT NULL REFERENCES relation_definition(id) ON DELETE RESTRICT,
    PRIMARY KEY (model_revision_id, relation_definition_id)
);

CREATE INDEX ix_model_revision_relation_revision ON model_revision_relation(model_revision_id);
CREATE INDEX ix_model_revision_relation_definition ON model_revision_relation(relation_definition_id);

CREATE TABLE model_revision_rule (
    model_revision_id    INTEGER NOT NULL REFERENCES model_revision(id) ON DELETE CASCADE,
    rule_definition_id   INTEGER NOT NULL REFERENCES rule_definition(id) ON DELETE RESTRICT,
    PRIMARY KEY (model_revision_id, rule_definition_id)
);

CREATE INDEX ix_model_revision_rule_revision ON model_revision_rule(model_revision_id);
CREATE INDEX ix_model_revision_rule_definition ON model_revision_rule(rule_definition_id);

-- ============================================================
-- 9. EXECUTION / OBSERVATION LAYER
-- ExecutionContext owns shared observed reality.
-- ModelExecution applies one immutable ModelRevision to that context.
-- ============================================================
CREATE TABLE execution_context (
    id              INTEGER PRIMARY KEY,
    uid             TEXT NOT NULL UNIQUE,
    workspace_id    INTEGER NOT NULL REFERENCES workspace(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,
    description     TEXT,
    started_at      TEXT,
    closed_at       TEXT,
    created_at      TEXT NOT NULL,
    CHECK (closed_at IS NULL OR started_at IS NULL OR closed_at >= started_at)
);

CREATE INDEX ix_execution_context_workspace ON execution_context(workspace_id);

CREATE TABLE model_execution (
    id                      INTEGER PRIMARY KEY,
    uid                     TEXT NOT NULL UNIQUE,
    execution_context_id    INTEGER NOT NULL REFERENCES execution_context(id) ON DELETE RESTRICT,
    model_revision_id       INTEGER NOT NULL REFERENCES model_revision(id) ON DELETE RESTRICT,
    name                    TEXT,
    started_at              TEXT,
    completed_at            TEXT,
    created_at              TEXT NOT NULL,
    CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
);

CREATE INDEX ix_model_execution_context ON model_execution(execution_context_id);
CREATE INDEX ix_model_execution_revision ON model_execution(model_revision_id);

CREATE TABLE entity_instance (
    id                      INTEGER PRIMARY KEY,
    uid                     TEXT NOT NULL UNIQUE,
    execution_context_id    INTEGER NOT NULL REFERENCES execution_context(id) ON DELETE RESTRICT,
    entity_definition_id    INTEGER NOT NULL REFERENCES entity_definition(id) ON DELETE RESTRICT,
    created_at              TEXT NOT NULL
);

CREATE INDEX ix_entity_instance_context ON entity_instance(execution_context_id);
CREATE INDEX ix_entity_instance_definition ON entity_instance(entity_definition_id);

CREATE TABLE model_execution_entity (
    model_execution_id  INTEGER NOT NULL REFERENCES model_execution(id) ON DELETE CASCADE,
    entity_instance_id  INTEGER NOT NULL REFERENCES entity_instance(id) ON DELETE RESTRICT,
    PRIMARY KEY (model_execution_id, entity_instance_id)
);

CREATE INDEX ix_model_execution_entity_instance ON model_execution_entity(entity_instance_id);

CREATE TABLE relation_instance (
    id                          INTEGER PRIMARY KEY,
    uid                         TEXT NOT NULL UNIQUE,
    execution_context_id        INTEGER NOT NULL REFERENCES execution_context(id) ON DELETE RESTRICT,
    semantic_id                 INTEGER NOT NULL REFERENCES relation_semantic(id) ON DELETE RESTRICT,
    source_entity_instance_id   INTEGER NOT NULL REFERENCES entity_instance(id) ON DELETE RESTRICT,
    target_entity_instance_id   INTEGER NOT NULL REFERENCES entity_instance(id) ON DELETE RESTRICT,
    relation_definition_id      INTEGER REFERENCES relation_definition(id) ON DELETE RESTRICT,
    created_at                  TEXT NOT NULL
);

CREATE INDEX ix_relation_instance_context ON relation_instance(execution_context_id);
CREATE INDEX ix_relation_instance_semantic ON relation_instance(semantic_id);
CREATE INDEX ix_relation_instance_source ON relation_instance(source_entity_instance_id);
CREATE INDEX ix_relation_instance_target ON relation_instance(target_entity_instance_id);
CREATE INDEX ix_relation_instance_definition ON relation_instance(relation_definition_id);

CREATE TABLE model_execution_relation (
    model_execution_id    INTEGER NOT NULL REFERENCES model_execution(id) ON DELETE CASCADE,
    relation_instance_id  INTEGER NOT NULL REFERENCES relation_instance(id) ON DELETE RESTRICT,
    PRIMARY KEY (model_execution_id, relation_instance_id)
);

CREATE INDEX ix_model_execution_relation_instance ON model_execution_relation(relation_instance_id);

-- ============================================================
-- 10. CURRENT INSTANCE VALUES + HISTORICAL OBSERVATIONS
-- ============================================================
CREATE TABLE instance_property_value (
    entity_instance_id         INTEGER NOT NULL REFERENCES entity_instance(id) ON DELETE CASCADE,
    property_definition_id     INTEGER NOT NULL REFERENCES property_definition(id) ON DELETE RESTRICT,
    value_text                 TEXT,
    value_integer              INTEGER,
    value_real                 REAL,
    value_boolean              INTEGER CHECK (value_boolean IS NULL OR value_boolean IN (0,1)),
    PRIMARY KEY (entity_instance_id, property_definition_id),
    CHECK (
        (value_text IS NOT NULL) +
        (value_integer IS NOT NULL) +
        (value_real IS NOT NULL) +
        (value_boolean IS NOT NULL) = 1
    )
);

CREATE TABLE property_observation (
    id                      INTEGER PRIMARY KEY,
    entity_instance_id      INTEGER NOT NULL REFERENCES entity_instance(id) ON DELETE CASCADE,
    property_definition_id  INTEGER NOT NULL REFERENCES property_definition(id) ON DELETE RESTRICT,
    value_text              TEXT,
    value_integer           INTEGER,
    value_real              REAL,
    value_boolean           INTEGER CHECK (value_boolean IS NULL OR value_boolean IN (0,1)),
    observed_at             TEXT NOT NULL,
    recorded_at             TEXT NOT NULL,
    CHECK (
        (value_text IS NOT NULL) +
        (value_integer IS NOT NULL) +
        (value_real IS NOT NULL) +
        (value_boolean IS NOT NULL) = 1
    )
);

CREATE INDEX ix_property_observation_lookup
    ON property_observation(entity_instance_id, property_definition_id, observed_at);

CREATE TABLE relation_instance_property_value (
    relation_instance_id       INTEGER NOT NULL REFERENCES relation_instance(id) ON DELETE CASCADE,
    property_definition_id     INTEGER NOT NULL REFERENCES property_definition(id) ON DELETE RESTRICT,
    value_text                 TEXT,
    value_integer              INTEGER,
    value_real                 REAL,
    value_boolean              INTEGER CHECK (value_boolean IS NULL OR value_boolean IN (0,1)),
    PRIMARY KEY (relation_instance_id, property_definition_id),
    CHECK (
        (value_text IS NOT NULL) +
        (value_integer IS NOT NULL) +
        (value_real IS NOT NULL) +
        (value_boolean IS NOT NULL) = 1
    )
);

-- ============================================================
-- 11. CORE SEED DATA
-- Fixed IDs are used only for deterministic core catalog seeds.
-- ============================================================
INSERT INTO entity_type
    (id, uid, workspace_id, parent_type_id, code, name, is_core)
VALUES
    (1, 'core:entity-type:process-group', NULL, NULL, 'PROCESS_GROUP', 'Process Group', 1),
    (2, 'core:entity-type:action',        NULL, NULL, 'ACTION',        'Action',        1),
    (3, 'core:entity-type:information',   NULL, NULL, 'INFORMATION',   'Information',   1),
    (4, 'core:entity-type:participant',   NULL, NULL, 'PARTICIPANT',   'Participant',   1),
    (5, 'core:entity-type:means',         NULL, NULL, 'MEANS',         'Means',         1),
    (6, 'core:entity-type:internal-function', NULL, 4, 'INTERNAL_FUNCTION', 'Internal Function', 1),
    (7, 'core:entity-type:external-party',    NULL, 4, 'EXTERNAL_PARTY',    'External Party',    1),
    (8, 'core:entity-type:role',              NULL, 4, 'ROLE',              'Role',              1),
    (9, 'core:entity-type:person',            NULL, 4, 'PERSON',            'Person',            1),
    (10,'core:entity-type:information-flow',  NULL, NULL, 'INFORMATION_FLOW','Information Flow', 1);

INSERT INTO relation_semantic
    (id, uid, workspace_id, code, name, description, inverse_label, is_core, is_symmetric, is_acyclic)
VALUES
    (1, 'core:relation:contains',  NULL, 'CONTAINS',  'Contains',  'Process containment relation.', 'Part of',       1, 0, 1),
    (2, 'core:relation:performer', NULL, 'PERFORMER', 'Performer', 'Participant performing an action.', 'Performs', 1, 0, 0),
    (3, 'core:relation:input',     NULL, 'INPUT',     'Input',     'Information used as input by an action.', NULL,  1, 0, 0),
    (4, 'core:relation:output',    NULL, 'OUTPUT',    'Output',    'Information produced by an action.', NULL,       1, 0, 0),
    (5, 'core:relation:means',     NULL, 'MEANS',     'Means',     'Means used by an action.', NULL,                 1, 0, 0),
    (6, 'core:relation:source',    NULL, 'SOURCE',    'Source',    'Source participant of a reified flow.', NULL,     1, 0, 0),
    (7, 'core:relation:target',    NULL, 'TARGET',    'Target',    'Target participant of a reified flow.', NULL,     1, 0, 0),
    (8, 'core:relation:carries',   NULL, 'CARRIES',   'Carries',   'Information carried by a reified flow.', NULL,    1, 0, 0),
    (9, 'core:relation:via',       NULL, 'VIA',       'Via',       'Means used by a reified flow.', NULL,             1, 0, 0);

-- Core relation signatures.
INSERT INTO relation_signature
    (relation_semantic_id, source_entity_type_id, target_entity_type_id)
VALUES
    (1, 1, 1), -- PROCESS_GROUP CONTAINS PROCESS_GROUP
    (1, 1, 2), -- PROCESS_GROUP CONTAINS ACTION
    (1, 1, 3), -- PROCESS_GROUP CONTAINS INFORMATION
    (2, 2, 4), -- ACTION PERFORMER PARTICIPANT (+ subtypes)
    (3, 2, 3), -- ACTION INPUT INFORMATION
    (4, 2, 3), -- ACTION OUTPUT INFORMATION
    (5, 2, 5), -- ACTION MEANS MEANS
    (6,10, 4), -- INFORMATION_FLOW SOURCE PARTICIPANT
    (7,10, 4), -- INFORMATION_FLOW TARGET PARTICIPANT
    (8,10, 3), -- INFORMATION_FLOW CARRIES INFORMATION
    (9,10, 5); -- INFORMATION_FLOW VIA MEANS

-- Core instance/definition properties.
INSERT INTO property_definition
    (id, uid, workspace_id, code, name, description, value_type, unit, scope, track_history, is_core)
VALUES
    (1, 'core:property:target-cycle-time', NULL, 'TARGET_CYCLE_TIME', 'Target Cycle Time', 'Expected/target cycle time.', 'DURATION', NULL, 'DEFINITION', 0, 1),
    (2, 'core:property:actual-start',      NULL, 'ACTUAL_START',      'Actual Start',      'Observed actual start timestamp.', 'DATETIME', NULL, 'INSTANCE', 0, 1),
    (3, 'core:property:actual-end',        NULL, 'ACTUAL_END',        'Actual End',        'Observed actual completion timestamp.', 'DATETIME', NULL, 'INSTANCE', 0, 1),
    (4, 'core:property:status',            NULL, 'STATUS',            'Status',            'Current/observed state or status.', 'ENUM', NULL, 'INSTANCE', 1, 1),
    (5, 'core:property:criticality',       NULL, 'CRITICALITY',       'Criticality',       'Domain criticality classification.', 'ENUM', NULL, 'DEFINITION', 0, 1),
    (6, 'core:property:cost',              NULL, 'COST',              'Cost',              'Cost value; currency semantics may be refined by workspace properties.', 'NUMBER', NULL, 'BOTH', 0, 1),
    (7, 'core:property:available-at',      NULL, 'AVAILABLE_AT',      'Available At',      'Timestamp at which information became available.', 'DATETIME', NULL, 'INSTANCE', 0, 1),
    (8, 'core:property:result',            NULL, 'RESULT',            'Result',            'Observed result/outcome.', 'ENUM', NULL, 'INSTANCE', 0, 1);

INSERT INTO property_applicability(property_definition_id, entity_type_id) VALUES
    (1,2), -- target cycle time: ACTION
    (2,2), -- actual start: ACTION
    (3,2), -- actual end: ACTION
    (4,2), -- status: ACTION
    (4,3), -- status: INFORMATION
    (5,2), -- criticality: ACTION
    (5,3), -- criticality: INFORMATION
    (6,2), -- cost: ACTION
    (6,3), -- cost: INFORMATION
    (7,3), -- available at: INFORMATION
    (8,2); -- result: ACTION

-- Expression engine operations. Semantics/typing live in the Python engine.
INSERT INTO operation_definition(code, name, min_args, max_args) VALUES
    ('AND',         'Logical AND',        2, NULL),
    ('OR',          'Logical OR',         2, NULL),
    ('NOT',         'Logical NOT',        1, 1),
    ('IMPLIES',     'Logical implication',2, 2),
    ('EQ',          'Equal',              2, 2),
    ('NEQ',         'Not equal',          2, 2),
    ('GT',          'Greater than',       2, 2),
    ('GTE',         'Greater or equal',   2, 2),
    ('LT',          'Less than',          2, 2),
    ('LTE',         'Less or equal',      2, 2),
    ('ADD',         'Add',                2, NULL),
    ('SUBTRACT',    'Subtract',           2, 2),
    ('MULTIPLY',    'Multiply',           2, NULL),
    ('DIVIDE',      'Divide',             2, 2),
    ('COUNT',       'Count',              1, 1),
    ('SUM',         'Sum',                1, 1),
    ('AVG',         'Average',            1, 1),
    ('MIN',         'Minimum',            1, 1),
    ('MAX',         'Maximum',            1, 1),
    ('FILTER',      'Filter set',         2, 2),
    ('EXISTS',      'Exists',             1, 1),
    ('ALL',         'All',                2, 2),
    ('ANY',         'Any',                2, 2),
    ('NOW',         'Current time',       0, 0),
    ('TIME',        'Time of',            1, 1),
    ('DURATION',    'Duration',           2, 2),
    ('UPSTREAM',    'Upstream graph query',1,1),
    ('DOWNSTREAM',  'Downstream graph query',1,1),
    ('ANCESTORS',   'Ancestor graph query',1,1),
    ('DESCENDANTS', 'Descendant graph query',1,1),
    ('LATEST',      'Latest item',        1, 1);

COMMIT;

-- ============================================================
-- DOMAIN-LAYER INVARIANTS (INTENTIONALLY NOT ENCODED AS TRIGGERS)
-- ============================================================
-- 1. Published/archived model revisions and definitions referenced by them
--    are immutable. Changes use clone + copy-on-write.
-- 2. A ModelRevision may include at most one EntityDefinition for each
--    EntityIdentity.
-- 3. All ModelRevision members must belong to the same workspace/model
--    universe as the ProcessModel owning the revision.
-- 4. Every RelationDefinition included in a ModelRevision must resolve both
--    endpoint EntityIdentities to EntityDefinitions included in that revision.
-- 5. Relation signatures must be valid, including inheritance through
--    EntityType.parent_type_id.
-- 6. Semantics marked is_acyclic must not form cycles in the relevant graph.
-- 7. Expression trees must have exactly one root, no cycles, valid parent
--    ownership, unique sibling positions where required, valid operation arity,
--    valid reference resolution, and compatible static types.
-- 8. ASSERTION rule bodies must evaluate to BOOLEAN.
-- 9. DERIVATION body result type must be compatible with its target property.
-- 10. ModelExecution.model_revision_id is immutable after creation.
-- 11. ModelExecution and associated Entity/Relation Instances must share the
--     same ExecutionContext.
-- 12. RelationInstance source, target and relation itself must share the same
--     ExecutionContext; relation signatures must be valid.
-- 13. Typed property/literal storage must match PropertyDefinition/literal type.
--     DATE, DATETIME, DURATION and ENUM are stored in TEXT in V1.
-- 14. Property scope/applicability must be enforced, including EntityType
--     inheritance.
-- 15. Hard delete is allowed only for unused draft/orphan data. Historical or
--     published/runtime-referenced data is retired/archived instead.
-- 16. Potential, Active and Realized graphs; parallelism; sequence; rework;
--     waiting; critical path; rule evaluations; deadlocks; KPIs and other
--     analytics are derived and are not authoritative persisted facts.
-- 17. Presentation/layout data (coordinates, lanes, colors, collapsed state,
--     arrow style) is deliberately outside this schema and must not encode
--     process semantics.
-- 18. Complex/n-ary domain relations are reified as Entity identities/
--     definitions/instances and connected using ordinary relation semantics.
-- 19. UNKNOWN is a logical evaluation state distinct from FALSE and from SQL
--     NULL; it is handled by the expression/rule engine.
