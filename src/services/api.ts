import { z } from "zod";
import {
  catalogSchema,
  projectListSchema,
  projectCreateSchema,
  stateRuleInputSchema,
  documentSchema,
  type ProcessDocument,
} from "../domain/model";
export async function request(
  path: string,
  init?: RequestInit,
): Promise<unknown> {
  const response = await fetch("/api" + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body: unknown = await response.json();
  if (!response.ok)
    throw new Error(z.object({ error: z.string() }).parse(body).error);
  return body;
}
export const revisionListSchema = z.array(
  z.object({
    id: z.number(),
    code: z.string(),
    purpose: z.string().nullable(),
    status: z.string(),
    modelId: z.number(),
    workspaceId: z.number(),
    name: z.string(),
  }),
);
export type RevisionEntry = z.infer<typeof revisionListSchema>[number];
export const api = {
  saveRule: async (rid: number, input: z.infer<typeof stateRuleInputSchema>) =>
    documentSchema.parse(
      await request(`/revisions/${rid}/rules`, {
        method: "POST",
        body: JSON.stringify(stateRuleInputSchema.parse(input)),
      }),
    ),
  deleteRule: async (rid: number, ruleId: number, version: number) =>
    documentSchema.parse(
      await request(`/revisions/${rid}/rules/${ruleId}`, {
        method: "DELETE",
        body: JSON.stringify({ version }),
      }),
    ),
  projects: async () => projectListSchema.parse(await request("/projects")),
  createProject: async (input: z.infer<typeof projectCreateSchema>) =>
    documentSchema.parse(
      await request("/projects", {
        method: "POST",
        body: JSON.stringify(projectCreateSchema.parse(input)),
      }),
    ),
  catalog: async () => catalogSchema.parse(await request("/catalog")),
  list: async () => revisionListSchema.parse(await request("/revisions")),
  read: async (id: number) =>
    documentSchema.parse(await request(`/revisions/${id}`)),
  save: async (d: ProcessDocument) =>
    documentSchema.parse(
      await request(`/revisions/${d.revision.id}`, {
        method: "PUT",
        body: JSON.stringify(d),
      }),
    ),
  clone: async (id: number, code: string, purpose: string) =>
    documentSchema.parse(
      await request(`/revisions/${id}/clone`, {
        method: "POST",
        body: JSON.stringify({ code, purpose }),
      }),
    ),
};
export function downloadDocument(doc: ProcessDocument) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(doc, null, 2)], {
      type: "application/json;charset=utf-8",
    }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `IPF-${doc.revision.code}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
