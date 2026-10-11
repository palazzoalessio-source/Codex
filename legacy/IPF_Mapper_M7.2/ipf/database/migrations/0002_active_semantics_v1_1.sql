-- IPF schema V1.1: generic, revision-versioned model parameters and rule purpose metadata.
-- Business-specific names/thresholds remain data; engine code remains unchanged.
ALTER TABLE rule_definition ADD COLUMN purpose TEXT NOT NULL DEFAULT 'GENERAL'
    CHECK (purpose IN ('GENERAL','APPLICABILITY','REQUIREMENT','ENABLEMENT'));

CREATE TABLE model_parameter_definition (
    id INTEGER PRIMARY KEY,
    uid TEXT NOT NULL UNIQUE,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    value_type TEXT NOT NULL CHECK(value_type IN ('BOOLEAN','INTEGER','NUMBER','TEXT','DATE','DATETIME','DURATION','ENUM')),
    description TEXT,
    created_at TEXT NOT NULL,
    retired_at TEXT,
    UNIQUE(workspace_id, code)
);

CREATE TABLE model_revision_parameter_value (
    model_revision_id INTEGER NOT NULL REFERENCES model_revision(id) ON DELETE CASCADE,
    parameter_definition_id INTEGER NOT NULL REFERENCES model_parameter_definition(id) ON DELETE RESTRICT,
    value_text TEXT,
    value_integer INTEGER,
    value_real REAL,
    value_boolean INTEGER CHECK(value_boolean IN (0,1)),
    PRIMARY KEY(model_revision_id, parameter_definition_id)
);
CREATE INDEX ix_revision_parameter_definition ON model_revision_parameter_value(parameter_definition_id);
