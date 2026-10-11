import type { ProcessDocument } from "./model";
export interface Arc {
  source: string;
  target: string;
  id: string;
  kind: "flow" | "dependency" | "information";
}
export function arcs(doc: ProcessDocument): Arc[] {
  const out: Arc[] = [];
  for (const f of doc.entities.filter((e) => e.type === "INFORMATION_FLOW")) {
    const rs = doc.relations.filter((r) => r.source === f.id);
    const source = rs.find((r) => r.semantic === "SOURCE")?.target,
      target = rs.find((r) => r.semantic === "TARGET")?.target;
    if (source && target) out.push({ source, target, id: f.id, kind: "flow" });
  }
  for (const r of doc.relations) {
    if (r.semantic === "OUTPUT") out.push({ ...r, kind: "information" });
    if (r.semantic === "INPUT")
      out.push({
        id: r.id,
        source: r.target,
        target: r.source,
        kind: "information",
      });
  }
  for (const r of doc.rules)
    if (
      r.purpose === "ENABLEMENT" &&
      r.target &&
      r.recipe &&
      "kind" in r.recipe
    )
      out.push({
        source: String(r.recipe.identity_id),
        target: r.target,
        id: String(r.id),
        kind: "dependency",
      });
  return out;
}
/** Iterative Tarjan SCC: linear graph traversal without a recursive stack limit. */
export function cycles(edges: Pick<Arc, "source" | "target">[]): string[][] {
  const adjacent = new Map<string, string[]>();
  for (const e of edges) {
    if (!adjacent.has(e.source)) adjacent.set(e.source, []);
    adjacent.get(e.source)!.push(e.target);
    if (!adjacent.has(e.target)) adjacent.set(e.target, []);
  }
  let index = 0;
  const indices = new Map<string, number>(),
    low = new Map<string, number>(),
    stack: string[] = [],
    active = new Set<string>(),
    result: string[][] = [];
  const enter = (v: string) => {
    indices.set(v, index);
    low.set(v, index++);
    stack.push(v);
    active.add(v);
  };
  for (const origin of adjacent.keys()) {
    if (indices.has(origin)) continue;
    enter(origin);
    const frames: { v: string; next: number; parent?: string }[] = [
      { v: origin, next: 0 },
    ];
    while (frames.length) {
      const frame = frames.at(-1)!,
        neighbors = adjacent.get(frame.v)!;
      if (frame.next < neighbors.length) {
        const target = neighbors[frame.next++];
        if (!indices.has(target)) {
          enter(target);
          frames.push({ v: target, next: 0, parent: frame.v });
        } else if (active.has(target))
          low.set(frame.v, Math.min(low.get(frame.v)!, indices.get(target)!));
        continue;
      }
      frames.pop();
      if (frame.parent)
        low.set(
          frame.parent,
          Math.min(low.get(frame.parent)!, low.get(frame.v)!),
        );
      if (low.get(frame.v) === indices.get(frame.v)) {
        const members: string[] = [];
        let member: string;
        do {
          member = stack.pop()!;
          active.delete(member);
          members.push(member);
        } while (member !== frame.v);
        if (members.length > 1 || neighbors.includes(frame.v))
          result.push(members.sort());
      }
    }
  }
  return result;
}
