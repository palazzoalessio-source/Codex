import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";
import { MeansIcon } from "./MeansIcon";
export function FlowEdge(props: EdgeProps) {
  const [path, x, y] = getSmoothStepPath(props);
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        style={props.style}
        markerEnd={props.markerEnd}
        interactionWidth={24}
      />
      <EdgeLabelRenderer>
        <div
          className="flow-caption nodrag nopan"
          title={String(props.data?.information ?? "Flusso informativo")}
          style={{
            transform: `translate(-50%, -50%) translate(${Number(props.data?.labelX ?? x)}px,${Number(props.data?.labelY ?? y)}px)`,
            color: props.style?.stroke,
          }}
        >
          <MeansIcon kind={props.data?.meansIcon} size={24} />
          <span>{props.label}</span>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
