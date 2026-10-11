import { memo } from "react";
import {
  Handle,
  Position,
  NodeResizer,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import {
  Zap,
  FileText,
  Users,
  Layers,
  GitBranch,
  Radio,
  AlertTriangle,
  LockKeyhole,
} from "lucide-react";
import type { Entity } from "../domain/model";
import { critical } from "../domain/analysis";
export type ProcessNodeData = {
  entity: Entity;
  lane?: boolean;
  editable: boolean;
  onResize?: (
    id: string,
    x: number,
    y: number,
    width: number,
    height: number,
  ) => void;
  [key: string]: unknown;
};
export type CanvasNode = Node<ProcessNodeData, "process">;
const icons = {
  ACTION: Zap,
  DECISION: GitBranch,
  INFORMATION: FileText,
  PROCESS_GROUP: Layers,
  MEANS: Radio,
};
export const ProcessNode = memo(function ProcessNode({
  data,
  selected,
  id,
}: NodeProps<CanvasNode>) {
  const e = data.entity,
    Icon = icons[e.type as keyof typeof icons] ?? Users;
  const isCritical = critical(e.properties.CRITICALITY),
    group = e.type === "PROCESS_GROUP";
  return (
    <div
      className={`process-node ${data.lane ? "lane-node" : ""} ${group ? "group-node" : ""} ${e.type === "INFORMATION" ? "information-node" : ""} ${isCritical ? "critical-node" : ""} ${selected ? "selected-node" : ""} ${e.layout.collapsed ? "collapsed-node" : ""}`}
    >
      {data.editable && (group || data.lane) && (
        <NodeResizer
          minWidth={group ? 240 : 300}
          minHeight={group ? 100 : 120}
          isVisible={selected && !e.layout.locked}
          onResizeEnd={(_evt, p) =>
            data.onResize?.(id, p.x, p.y, p.width, p.height)
          }
        />
      )}
      {!data.lane && (
        <Handle
          type="target"
          position={Position.Left}
          isConnectable={data.editable && !e.layout.locked}
        />
      )}
      <div className="node-heading">
        <Icon size={15} />
        <span>{e.code || e.type.replaceAll("_", " ")}</span>
        {e.layout.locked && <LockKeyhole size={12} />}{" "}
        {isCritical && (
          <AlertTriangle
            size={16}
            className="critical-marker"
            aria-label="Criticità"
          />
        )}
      </div>
      <strong>{e.name}</strong>
      {group && (
        <small>
          {e.layout.collapsed
            ? "Gruppo chiuso · doppio clic per espandere"
            : "Gruppo · trascina per spostare i membri"}
        </small>
      )}
      {!data.lane && !group && (
        <div className="node-meta">
          {e.properties.TARGET_CYCLE_TIME && (
            <span>T/C {String(e.properties.TARGET_CYCLE_TIME)}</span>
          )}
          {(e.type === "ACTION" || e.type === "DECISION") && (
            <span className={`value-chip value-${e.classification}`}>
              {e.classification === "UNCLASSIFIED"
                ? "Da classificare"
                : e.classification}
            </span>
          )}
        </div>
      )}
      {!data.lane && (
        <Handle
          type="source"
          position={Position.Right}
          isConnectable={data.editable && !e.layout.locked}
        />
      )}
    </div>
  );
});
