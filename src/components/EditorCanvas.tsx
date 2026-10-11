import { useEffect, useMemo, useState, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  applyNodeChanges,
  useReactFlow,
  useViewport,
  MarkerType,
  getViewportForBounds,
  type Edge,
  type Connection,
  type NodeChange,
} from "@xyflow/react";
import { ProcessNode, ParticipantAnchor, type CanvasNode } from "./ProcessNode";
import {
  isType,
  type Catalog,
  type ProcessDocument,
  type Entity,
} from "../domain/model";
import { critical } from "../domain/analysis";
import { applyCommand, type Command } from "../domain/commands";
import { FlowEdge } from "./FlowEdge";
import { presentationLayouts } from "../domain/presentation";
import referenceLayout from "../../legacy/IPF_Mapper_M7.2/ipf/ui/reference_layout.json";
const edgeTypes = { flow: FlowEdge };
const nodeTypes = { process: ProcessNode, participant: ParticipantAnchor };

export function EditorCanvas({
  doc,
  catalog,
  dispatch,
  onSelect,
  onSelection,
  onConnect,
  onFlow,
  onViewport,
  focusId,
  grid,
  search,
  panMode,
}: {
  doc: ProcessDocument;
  catalog: Catalog;
  dispatch: (c: Command) => void;
  onSelect: (e: Entity | null) => void;
  onSelection: (ids: string[]) => void;
  onConnect: (c: Connection) => void;
  onFlow: (id: string, connection?: Connection) => void;
  onViewport: (v: { x: number; y: number; zoom: number }) => void;
  focusId: string | null;
  grid: boolean;
  search: string;
  panMode: boolean;
}) {
  const { setCenter, setViewport, screenToFlowPosition } = useReactFlow(),
    viewport = useViewport();
  const [size, setSize] = useState({ width: 1100, height: 700 }),
    [container, setContainer] = useState<HTMLDivElement | null>(null),
    [nodes, setNodes] = useState<CanvasNode[]>([]),
    [showMeans, setShowMeans] = useState(false);
  const editable = doc.revision.status === "DRAFT";
  const handleSelection = useCallback(
    ({ nodes }: { nodes: CanvasNode[] }) => onSelection(nodes.map((n) => n.id)),
    [onSelection],
  );
  const handleNodeChanges = useCallback(
    (changes: NodeChange<CanvasNode>[]) =>
      setNodes((n) => applyNodeChanges(changes, n)),
    [],
  );
  useEffect(() => {
    if (!container) return;
    const observer = new ResizeObserver(([entry]) =>
      setSize({
        width: Math.max(1, entry.contentRect.width - 140),
        height: entry.contentRect.height,
      }),
    );
    observer.observe(container);
    return () => observer.disconnect();
  }, [container]);
  const parent = useMemo(
    () =>
      new Map(
        doc.relations
          .filter((r) => r.semantic === "CONTAINS")
          .map((r) => [r.target, r.source]),
      ),
    [doc.relations],
  );
  const geometry = useMemo(
    () => presentationLayouts(doc),
    [doc.entities, doc.relations],
  );
  const hidden = useMemo(() => {
    const result = new Map<string, string>();
    for (const entity of doc.entities) {
      let p = parent.get(entity.id);
      const seen = new Set<string>();
      while (p && !seen.has(p)) {
        seen.add(p);
        if (doc.entities.find((e) => e.id === p)?.layout.collapsed)
          result.set(entity.id, p);
        p = parent.get(p);
      }
    }
    return result;
  }, [doc.entities, parent]);
  const resize = useCallback(
    (id: string, x: number, y: number, width: number, height: number) => {
      const p = parent.get(id),
        offset = p ? geometry.get(p) : null;
      dispatch({
        type: "move",
        positions: [
          {
            id,
            x: x + (offset?.x ?? 0),
            y: y + (offset?.y ?? 0),
            width,
            height,
          },
        ],
      });
    },
    [dispatch, parent, geometry],
  );
  const projected = useMemo(() => {
    const depth = (id: string): number => {
      let count = 0,
        p = parent.get(id);
      const seen = new Set<string>();
      while (p && !seen.has(p)) {
        seen.add(p);
        count++;
        p = parent.get(p);
      }
      return count;
    };
    return doc.entities
      .filter(
        (e) =>
          e.type !== "INFORMATION_FLOW" &&
          (showMeans || e.type !== "MEANS" || e.id === focusId) &&
          (!isType(e.type, "PARTICIPANT", catalog) ||
            doc.relations.some(
              (r) =>
                ["SOURCE", "TARGET"].includes(r.semantic) && r.target === e.id,
            )) &&
          !hidden.has(e.id),
      )
      .sort((a, b) => depth(a.id) - depth(b.id))
      .map((entity): CanvasNode => {
        const lane = isType(entity.type, "PARTICIPANT", catalog),
          group = entity.type === "PROCESS_GROUP",
          g = geometry.get(entity.id)!,
          p = parent.get(entity.id),
          offset = p ? geometry.get(p) : null;
        return {
          id: entity.id,
          type: lane ? "participant" : "process",
          parentId: lane ? undefined : p,
          position: lane
            ? { x: 0, y: g.y + 40 }
            : { x: g.x - (offset?.x ?? 0), y: g.y - (offset?.y ?? 0) },
          data: {
            entity,
            lane,
            editable: editable && !panMode,
            onResize: resize,
          },
          draggable: editable && !panMode && !lane && !entity.layout.locked,
          connectable: editable && !panMode && !entity.layout.locked,
          selectable: !panMode && !lane,
          zIndex: lane ? -20 : group ? -5 : 5,
          style: {
            width: lane
              ? 1
              : group
                ? entity.layout.collapsed
                  ? 240
                  : (g.width ?? 460)
                : (g.width ?? 200),
            height: lane
              ? 1
              : group
                ? entity.layout.collapsed
                  ? 100
                  : (g.height ?? 240)
                : (g.height ?? 94),
            opacity:
              search &&
              !entity.name
                .toLocaleLowerCase()
                .includes(search.toLocaleLowerCase())
                ? 0.35
                : 1,
          },
        };
      });
  }, [
    doc.entities,
    doc.relations,
    catalog,
    parent,
    geometry,
    hidden,
    editable,
    panMode,
    resize,
    search,
    showMeans,
    focusId,
  ]);
  useEffect(() => {
    setNodes((old) =>
      projected.map((n) => ({
        ...n,
        selected: old.find((o) => o.id === n.id)?.selected ?? false,
      })),
    );
  }, [projected]);
  const fitProcess = () => {
    const bounds = doc.entities
      .filter(
        (e) =>
          e.type !== "INFORMATION_FLOW" &&
          (showMeans || e.type !== "MEANS" || e.id === focusId) &&
          !isType(e.type, "PARTICIPANT", catalog) &&
          !hidden.has(e.id),
      )
      .map((e) => {
        const g = geometry.get(e.id)!;
        return {
          x: g.x,
          y: g.y,
          width:
            e.type === "PROCESS_GROUP"
              ? e.layout.collapsed
                ? 240
                : (g.width ?? 460)
              : (g.width ?? 200),
          height:
            e.type === "PROCESS_GROUP"
              ? e.layout.collapsed
                ? 100
                : (g.height ?? 240)
              : (g.height ?? 94),
        };
      });
    if (!bounds.length) return Promise.resolve(false);
    const x = Math.min(...bounds.map((b) => b.x)),
      y = Math.min(...bounds.map((b) => b.y));
    const width = Math.max(...bounds.map((b) => b.x + b.width)) - x,
      height = Math.max(...bounds.map((b) => b.y + b.height)) - y;
    return setViewport(
      getViewportForBounds(
        { x, y, width, height },
        size.width,
        size.height,
        0.05,
        0.9,
        0.12,
      ),
      { duration: 350 },
    );
  };
  useEffect(() => {
    void setViewport(doc.viewport);
    if (doc.viewport.x === 0 && doc.viewport.y === 0) {
      const timer = setTimeout(() => {
        const visible = doc.entities.filter(
          (e) =>
            e.type !== "INFORMATION_FLOW" &&
            (showMeans || e.type !== "MEANS" || e.id === focusId) &&
            !isType(e.type, "PARTICIPANT", catalog) &&
            !hidden.has(e.id),
        );
        if (visible.length)
          void setViewport({
            x: 170 - Math.min(...visible.map((e) => geometry.get(e.id)!.x)),
            y: 70 - Math.min(...visible.map((e) => geometry.get(e.id)!.y)),
            zoom: 1,
          });
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [doc.revision.id, setViewport]);
  useEffect(() => {
    if (!focusId) return;
    const target = geometry.get(hidden.get(focusId) ?? focusId);
    setNodes((n) =>
      n.map((node) => ({
        ...node,
        selected: node.id === (hidden.get(focusId) ?? focusId),
      })),
    );
    if (target)
      void setCenter(
        target.x + (target.width ?? 200) / 2,
        target.y + (target.height ?? 94) / 2,
        {
          zoom: 1,
          duration: 400,
        },
      );
  }, [focusId, doc.revision.id, setCenter]);
  const edges = useMemo(() => {
    const result: Edge[] = [],
      by = new Map(doc.entities.map((e) => [e.id, e]));
    const project = (id: string) => hidden.get(id) ?? id;
    for (const flow of doc.entities.filter(
      (e) => e.type === "INFORMATION_FLOW",
    )) {
      const rs = doc.relations.filter((r) => r.source === flow.id),
        source = rs.find((r) => r.semantic === "SOURCE")?.target,
        target = rs.find((r) => r.semantic === "TARGET")?.target;
      if (!source || !target || project(source) === project(target)) continue;
      const via = rs.find((r) => r.semantic === "VIA")?.target,
        info = rs.find((r) => r.semantic === "CARRIES")?.target;
      const isCritical = [
        flow,
        by.get(source),
        by.get(target),
        info ? by.get(info) : null,
      ].some((e) => e && critical(e.properties.CRITICALITY));
      result.push({
        id: "flow:" + flow.id,
        source: project(source),
        target: project(target),
        type: "flow",
        reconnectable: editable && !hidden.has(source) && !hidden.has(target),
        label: [
          via ? by.get(via)?.name : null,
          flow.properties.TARGET_LEAD_TIME,
        ]
          .filter(Boolean)
          .join(" · "),
        style: {
          stroke: isCritical ? "#df3449" : "#6f849d",
          strokeWidth: isCritical ? 2.8 : 1.7,
        },
        labelStyle: { fontSize: 11, fill: isCritical ? "#bb263c" : "#455a72" },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isCritical ? "#df3449" : "#6f849d",
        },
        data: {
          ...(() => {
            const sourceEntity = by.get(source)!,
              targetEntity = by.get(target)!;
            const presets = referenceLayout.nodes as Record<
              string,
              { baseline: number[]; rect: number[] }
            >;
            const badges = referenceLayout.badges as Record<string, number[]>;
            const badge = badges[`${sourceEntity.code}|${targetEntity.code}`];
            const untouched = (e: Entity) => {
              const p = presets[e.code];
              return (
                p &&
                !e.layout.width &&
                e.layout.x === p.baseline[0] &&
                e.layout.y === p.baseline[1]
              );
            };
            return badge &&
              untouched(sourceEntity) &&
              untouched(targetEntity) &&
              geometry.get(source)?.x !== sourceEntity.layout.x
              ? { labelX: badge[0] * 1.5, labelY: badge[1] * 1.5 }
              : {};
          })(),
          information: info ? by.get(info)?.name : null,
          flowId: flow.id,
          meansIcon: via
            ? (by.get(via)?.properties.MEANS_ICON ?? "Generic")
            : "Generic",
        },
      });
    }
    for (const r of doc.relations.filter(
      (r) =>
        ![
          "CONTAINS",
          "PERFORMER",
          "SOURCE",
          "TARGET",
          "VIA",
          "CARRIES",
        ].includes(r.semantic),
    )) {
      const source = project(r.semantic === "INPUT" ? r.target : r.source),
        target = project(r.semantic === "INPUT" ? r.source : r.target);
      if (source === target) continue;
      result.push({
        id: "relation:" + r.id,
        source,
        target,
        label: r.semantic,
        type: "smoothstep",
        style: { stroke: "#9aaabe", strokeDasharray: "5 4" },
        markerEnd: { type: MarkerType.ArrowClosed },
        data: { relationId: r.id },
      });
    }
    return result;
  }, [doc, hidden, editable, geometry]);
  const commitPositions = (draggedId: string) => {
    const by = new Map(nodes.map((n) => [n.id, n]));
    const absolute = (
      n: CanvasNode,
      seen = new Set<string>(),
    ): { x: number; y: number } => {
      if (!n.parentId || seen.has(n.id)) return n.position;
      seen.add(n.id);
      const p = by.get(n.parentId);
      if (!p) return n.position;
      const at = absolute(p, seen);
      return { x: n.position.x + at.x, y: n.position.y + at.y };
    };
    const positions = nodes
      .filter((n) => !n.data.lane)
      .map((n) => ({ id: n.id, ...absolute(n) }))
      .filter((p) => {
        const g = geometry.get(p.id);
        return g && (Math.abs(g.x - p.x) > 0.1 || Math.abs(g.y - p.y) > 0.1);
      });
    if (positions.length) {
      let next = applyCommand(doc, { type: "move", positions }, catalog);
      const dragged = doc.entities.find((e) => e.id === draggedId);
      if (dragged && isType(dragged.type, "ACTION", catalog)) {
        const lanes = doc.entities
          .filter((e) => isType(e.type, "PARTICIPANT", catalog))
          .sort((a, b) => a.layout.y - b.layout.y);
        for (const p of positions) {
          const entity = next.entities.find((e) => e.id === p.id);
          if (!entity || !isType(entity.type, "ACTION", catalog)) continue;
          const lane = lanes.find(
            (l, n) =>
              p.y + 40 >= geometry.get(l.id)!.y &&
              p.y + 40 <
                ((lanes[n + 1]
                  ? geometry.get(lanes[n + 1].id)!.y
                  : undefined) ??
                  geometry.get(l.id)!.y + (geometry.get(l.id)!.height ?? 140)),
          );
          if (lane)
            next = applyCommand(
              next,
              {
                type: "relation",
                relation: {
                  id: crypto.randomUUID(),
                  semantic: "PERFORMER",
                  source: p.id,
                  target: lane.id,
                },
              },
              catalog,
            );
        }
      }
      dispatch({ type: "replace", document: next });
    }
  };
  return (
    <div
      className="canvas-area"
      ref={setContainer}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }}
      onDrop={(e) => {
        e.preventDefault();
        const type = e.dataTransfer.getData("application/ipf-type");
        if (
          !catalog.types.some((t) => t.code === type) ||
          type === "INFORMATION_FLOW" ||
          !editable
        )
          return;
        const { x, y } = screenToFlowPosition({ x: e.clientX, y: e.clientY });
        const entity: Entity = {
          id: crypto.randomUUID(),
          uid: crypto.randomUUID(),
          type,
          name: catalog.types.find((t) => t.code === type)?.name ?? type,
          description: "",
          code: "",
          properties: {},
          classification: "UNCLASSIFIED",
          layout: {
            x,
            y,
            collapsed: false,
            locked: false,
            ...(type === "PROCESS_GROUP" ? { width: 460, height: 260 } : {}),
          },
        };
        dispatch({ type: "upsert", entity });
        onSelect(entity);
      }}
    >
      <div className="lane-backgrounds" aria-hidden="true">
        {doc.entities
          .filter((e) => isType(e.type, "PARTICIPANT", catalog))
          .sort((a, b) => a.layout.y - b.layout.y)
          .map((e, i, lanes) => {
            const top = geometry.get(e.id)!.y * viewport.zoom + viewport.y;
            const bottom = lanes[i + 1]
              ? geometry.get(lanes[i + 1].id)!.y * viewport.zoom + viewport.y
              : Math.max(
                  size.height,
                  top + (geometry.get(e.id)!.height ?? 140) * viewport.zoom,
                );
            return (
              <div
                key={e.id}
                className="lane-band"
                style={{
                  top: i === 0 ? Math.min(0, top) : top,
                  height: bottom - (i === 0 ? Math.min(0, top) : top),
                  background: [
                    "#edf5ff",
                    "#edf9f2",
                    "#f3edfb",
                    "#fcf7e9",
                    "#faedf1",
                    "#eaf3f9",
                  ][i % 6],
                }}
              />
            );
          })}
      </div>
      <div className="flow-surface">
        <ReactFlow<CanvasNode>
          className={panMode ? "mode-pan" : "mode-select"}
          nodesDraggable={!panMode && editable}
          nodesConnectable={!panMode && editable}
          elementsSelectable={!panMode}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={handleNodeChanges}
          onNodeDragStop={(_event, node) => commitPositions(node.id)}
          onNodeClick={(_e, n) => {
            if (!panMode) onSelect(n.data.entity);
          }}
          onNodeDoubleClick={(_e, n) => {
            if (!panMode && n.data.entity.type === "PROCESS_GROUP" && editable)
              dispatch({
                type: "upsert",
                entity: {
                  ...n.data.entity,
                  layout: {
                    ...n.data.entity.layout,
                    collapsed: !n.data.entity.layout.collapsed,
                  },
                },
              });
          }}
          onPaneClick={() => {
            if (!panMode) onSelect(null);
          }}
          onSelectionChange={handleSelection}
          onConnect={onConnect}
          onEdgeClick={(_e, edge) => {
            if (edge.data?.flowId) onFlow(String(edge.data.flowId));
            else if (edge.data?.relationId) {
              const r = doc.relations.find(
                (r) => r.id === String(edge.data?.relationId),
              );
              if (r) {
                onSelect(doc.entities.find((e) => e.id === r.source) ?? null);
              }
            }
          }}
          onReconnect={(edge, c) => {
            if (edge.data?.flowId) onFlow(String(edge.data.flowId), c);
            else {
              const id = String(edge.data?.relationId ?? "");
              const relation = doc.relations.find((r) => r.id === id);
              if (relation && c.source && c.target) {
                const source =
                    relation.semantic === "INPUT" ? c.target : c.source,
                  target = relation.semantic === "INPUT" ? c.source : c.target;
                dispatch({
                  type: "replace",
                  document: {
                    ...doc,
                    relations: doc.relations.map((r) =>
                      r.id === id ? { ...r, source, target } : r,
                    ),
                  },
                });
              }
            }
          }}
          onMoveEnd={(_e, v) => onViewport(v)}
          snapToGrid={grid}
          snapGrid={[20, 20]}
          minZoom={0.05}
          maxZoom={2.5}
          panOnDrag={panMode ? [0, 1, 2] : [1, 2]}
          selectionOnDrag={!panMode}
          selectionKeyCode="Shift"
          multiSelectionKeyCode={["Control", "Meta"]}
          deleteKeyCode={null}
          nodesFocusable
          edgesFocusable
          onlyRenderVisibleElements
          defaultViewport={doc.viewport}
          fitView={false}
          fitViewOptions={{ padding: 0.15, maxZoom: 0.9 }}
        >
          {grid && <Background gap={20} size={1} color="#bdcad7" />}
          <Controls
            showInteractive={false}
            showFitView={false}
            fitViewOptions={{
              nodes: doc.entities
                .filter(
                  (e) =>
                    e.type !== "INFORMATION_FLOW" &&
                    (showMeans || e.type !== "MEANS" || e.id === focusId) &&
                    !isType(e.type, "PARTICIPANT", catalog),
                )
                .map((e) => ({ id: e.id })),
              padding: 0.12,
              maxZoom: 0.9,
            }}
          />
          <MiniMap
            pannable
            zoomable
            nodeColor={(n) => {
              const e = (n as CanvasNode).data.entity;
              return critical(e.properties.CRITICALITY)
                ? "#df3449"
                : e.type === "PROCESS_GROUP"
                  ? "#9caabe"
                  : "#608eac";
            }}
            maskColor="rgba(228,235,244,0.75)"
          />
        </ReactFlow>
      </div>
      <div className="lane-labels">
        {doc.entities
          .filter((e) => isType(e.type, "PARTICIPANT", catalog))
          .map((e) => (
            <div
              key={e.id}
              className="lane-label"
              style={{
                top: geometry.get(e.id)!.y * viewport.zoom + viewport.y,
              }}
            >
              <span>{e.code || "FUNZIONE"}</span>
              <strong>{e.name}</strong>
            </div>
          ))}
      </div>
      <div className="canvas-hint">
        {panMode
          ? "Trascina lo sfondo per navigare"
          : "Trascina per selezionare"}{" "}
        · Space per pan · Shift per selezione · doppio clic sui gruppi
      </div>
      {!doc.entities.length && (
        <div className="empty-canvas">
          <h2>Il tuo processo inizia qui</h2>
          <p>
            Trascina un elemento dalla libreria o clicca sul tipo da aggiungere.
          </p>
          <p>
            Aggiungi una funzione per creare la prima lane, poi le attività e i
            flussi.
          </p>
        </div>
      )}
      <div className="canvas-view-tools">
        <button onClick={() => void setViewport({ ...viewport, zoom: 1 })}>
          100%
        </button>
        <button
          aria-pressed={showMeans}
          onClick={() => setShowMeans(!showMeans)}
        >
          Mezzi {showMeans ? "visibili" : "nascosti"}
        </button>
      </div>
      <button className="fit-button" onClick={() => void fitProcess()}>
        Adatta processo
      </button>
    </div>
  );
}
