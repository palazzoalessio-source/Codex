import type { ProcessDocument } from "./model";
import referenceLayout from "../../legacy/IPF_Mapper_M7.2/ipf/ui/reference_layout.json";
export function presentationLayouts(doc: ProcessDocument) {
  const parent = new Map(
    doc.relations
      .filter((r) => r.semantic === "CONTAINS")
      .map((r) => [r.target, r.source]),
  );
  const result = new Map(doc.entities.map((e) => [e.id, { ...e.layout }]));
  // Same presentation preset as the approved Python canvas; model coordinates remain untouched until an explicit drag.
  const codes = new Set(doc.entities.map((e) => e.code));
  if (Object.keys(referenceLayout.nodes).every((code) => codes.has(code))) {
    const presets = referenceLayout.nodes as Record<
      string,
      { baseline: number[]; rect: number[] }
    >;
    const lanes = referenceLayout.lanes as Record<string, number[]>;
    const baseline = referenceLayout.baseline_functions as Record<
      string,
      number
    >;
    for (const e of doc.entities) {
      const preset = presets[e.code];
      if (
        preset &&
        !e.layout.width &&
        e.layout.x === preset.baseline[0] &&
        e.layout.y === preset.baseline[1]
      )
        result.set(e.id, {
          ...e.layout,
          x: preset.rect[0] * 1.5,
          y: preset.rect[1] * 1.5,
          width: (preset.rect[2] || 135) * 1.5,
          height: (preset.rect[3] || 50) * 1.5,
        });
      if (lanes[e.code] && e.layout.y === baseline[e.code])
        result.set(e.id, {
          ...e.layout,
          y: lanes[e.code][0] * 1.5,
          height: lanes[e.code][1] * 1.5,
        });
    }
  }
  const groups = doc.entities.filter((e) => e.type === "PROCESS_GROUP");
  for (let n = 0; n < groups.length; n++)
    for (const group of groups) {
      if (group.layout.width && group.layout.height) continue;
      const members = doc.entities
        .filter((e) => parent.get(e.id) === group.id)
        .map((e) => result.get(e.id)!);
      if (!members.length) continue;
      const x = Math.min(...members.map((e) => e.x)) - 30,
        y = Math.min(...members.map((e) => e.y)) - 55;
      result.set(group.id, {
        ...group.layout,
        x,
        y,
        width: Math.max(...members.map((e) => e.x + (e.width ?? 200))) - x + 30,
        height:
          Math.max(...members.map((e) => e.y + (e.height ?? 90))) - y + 25,
      });
    }
  return result;
}
