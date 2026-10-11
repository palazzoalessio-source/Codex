PRAGMA foreign_keys=ON;
BEGIN;
CREATE TABLE IF NOT EXISTS model_revision_view (
    model_revision_id INTEGER PRIMARY KEY REFERENCES model_revision(id) ON DELETE CASCADE,
    zoom REAL NOT NULL DEFAULT 1.0,
    pan_x REAL NOT NULL DEFAULT 0,
    pan_y REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entity_view_layout (
    model_revision_id INTEGER NOT NULL REFERENCES model_revision(id) ON DELETE CASCADE,
    entity_identity_id INTEGER NOT NULL REFERENCES entity_identity(id) ON DELETE CASCADE,
    x REAL NOT NULL DEFAULT 0,
    y REAL NOT NULL DEFAULT 0,
    width REAL,
    height REAL,
    collapsed INTEGER NOT NULL DEFAULT 0 CHECK(collapsed IN (0,1)),
    z_index REAL NOT NULL DEFAULT 0,
    PRIMARY KEY(model_revision_id,entity_identity_id)
);
CREATE INDEX IF NOT EXISTS ix_entity_view_layout_revision ON entity_view_layout(model_revision_id);

-- Visual IPF needs flow endpoints at action level as well as participant level.
INSERT OR IGNORE INTO relation_signature(relation_semantic_id,source_entity_type_id,target_entity_type_id) VALUES
 (6,10,2), -- INFORMATION_FLOW SOURCE ACTION
 (7,10,2); -- INFORMATION_FLOW TARGET ACTION

-- Transition lead time is a property of the reified information flow.
INSERT OR IGNORE INTO property_definition(id,uid,workspace_id,code,name,description,value_type,unit,scope,track_history,is_core)
VALUES(9,'core:property:target-lead-time',NULL,'TARGET_LEAD_TIME','Target Lead Time','Expected traversal time between process elements.','DURATION',NULL,'DEFINITION',0,1);
INSERT OR IGNORE INTO property_applicability(property_definition_id,entity_type_id) VALUES(9,10);

-- Optional note explaining why an Action/Information is marked critical.
INSERT OR IGNORE INTO property_definition(id,uid,workspace_id,code,name,description,value_type,unit,scope,track_history,is_core)
VALUES(10,'core:property:criticality-note',NULL,'CRITICALITY_NOTE','Criticality Note','Optional explanation of the IPF criticality marker.','TEXT',NULL,'DEFINITION',0,1);
INSERT OR IGNORE INTO property_applicability(property_definition_id,entity_type_id) VALUES(10,2),(10,3);
COMMIT;
