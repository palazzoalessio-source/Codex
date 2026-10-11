import { test, expect } from "@playwright/test";

test("apertura legacy, proprietà UTF-8, valore operativo, save/reload e analisi", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "DEMO — Procurement RFQ AS-IS" }),
  ).toBeVisible();
  await page.getByLabel("Cerca nel processo").fill("Analizza offerte");
  await page
    .locator(".element-list")
    .getByRole("button", { name: "Analizza offerte", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Proprietà", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Nome elemento")
    .fill("Analizza offerte — qualità è già pronta");
  await page.getByLabel("Classificazione valore").selectOption("VA");
  await page.getByRole("button", { name: "Applica proprietà" }).click();
  await expect(page.locator(".heading-status")).toContainText("Salvato", {
    timeout: 10000,
  });
  await page.reload();
  await page.getByLabel("Cerca nel processo").fill("Analizza offerte");
  await page
    .locator(".element-list button")
    .filter({ hasText: "Analizza offerte — qualità è già pronta" })
    .click();
  await expect(page.getByLabel("Classificazione valore")).toHaveValue("VA");
  await page.getByRole("button", { name: "Analisi", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Analisi del modello" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Validazione/ }).click();
  await expect(page.locator(".analysis-content")).not.toContainText(
    "INVALID_SIGNATURE",
  );
  expect(errors).toEqual([]);
  await page.screenshot({ path: ".local/editor-verified.png", fullPage: true });
});
test("gruppo da libreria, proprietà, undo e redo", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".library")).toBeVisible();
  await page
    .locator(".library button")
    .filter({ hasText: "Process Group" })
    .click();
  await page.getByLabel("Nome elemento").fill("Gruppo browser");
  await page.getByRole("button", { name: "Applica proprietà" }).click();
  await expect(page.locator(".heading-status")).toContainText("Salvato", {
    timeout: 10000,
  });
  await page.getByTitle("Annulla (Ctrl+Z)").click();
  await page.getByTitle("Ripeti (Ctrl+Shift+Z)").click();
  await expect(page.locator(".element-list")).toContainText("Gruppo browser");
  await page.reload();
  await expect(page.locator(".element-list")).toContainText("Gruppo browser");
});
test("creazione TO-BE e confronto stabile senza modificare AS-IS", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Copia revisione" }).click();
  await page.getByLabel("Codice revisione").fill("TO-BE-browser");
  await page.getByRole("button", { name: "Crea revisione" }).click();
  await expect(page.getByLabel("Revisione corrente")).toContainText(
    "TO-BE-browser",
  );
  await page.getByRole("button", { name: "Analisi", exact: true }).click();
  await page
    .getByRole("button", { name: "AS-IS / TO-BE", exact: true })
    .click();
  await page.getByLabel("Revisione di riferimento").selectOption("1");
  await expect(page.locator(".comparison-heading")).toContainText(
    "TO-BE-browser",
  );
  await expect(page.locator(".analysis-content")).toContainText(
    "Relazioni aggiunte: 0",
  );
});
test("drag-and-drop gruppo reale sul canvas e persistenza", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".library")).toBeVisible();
  const data = await page.evaluateHandle(() => new DataTransfer());
  await page
    .locator(".library button")
    .filter({ hasText: "Process Group" })
    .dispatchEvent("dragstart", { dataTransfer: data });
  await page
    .locator(".canvas-area")
    .dispatchEvent("drop", { dataTransfer: data, clientX: 700, clientY: 400 });
  await expect(page.getByLabel("Nome elemento")).toHaveValue("Process Group");
  await page.getByLabel("Nome elemento").fill("Gruppo drag & drop");
  await page.getByRole("button", { name: "Applica proprietà" }).click();
  await expect(page.locator(".heading-status")).toContainText("Salvato", {
    timeout: 10000,
  });
  await page.reload();
  await expect(page.locator(".element-list")).toContainText(
    "Gruppo drag & drop",
  );
});

test("handles creano un flow, drag sposta un nodo e pan/zoom persistono", async ({
  page,
  request,
}) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (e) => browserErrors.push(e.message));
  await page.goto("/");
  await expect(page.locator(".library")).toBeVisible();
  for (const name of ["Attività browser A", "Attività browser B"]) {
    await page
      .locator(".library")
      .getByRole("button", { name: /^Action/ })
      .click();
    await page.getByLabel("Nome elemento").fill(name);
    await page.getByRole("button", { name: "Applica proprietà" }).click();
    await expect(page.locator(".heading-status")).toContainText("Salvato", {
      timeout: 10000,
    });
  }
  const getDoc = async () => {
    const rid = await page.getByLabel("Revisione corrente").inputValue();
    return (await request.get(`/api/revisions/${rid}`)).json();
  };
  const d = await getDoc();
  const a = d.entities.find(
      (e: { name: string }) => e.name === "Attività browser A",
    ),
    b = d.entities.find(
      (e: { name: string }) => e.name === "Attività browser B",
    );
  await page.getByRole("button", { name: "Chiudi proprietà" }).click();
  await page
    .getByRole("button", { name: "Adatta processo", exact: true })
    .click();
  await page.waitForTimeout(400); // Fit animates for 350 ms; both handles must be in the viewport.
  const source = page.locator(
      `.react-flow__node[data-id="${a.id}"] .react-flow__handle.source`,
    ),
    target = page.locator(
      `.react-flow__node[data-id="${b.id}"] .react-flow__handle.target`,
    );
  await expect(source).toBeVisible();
  await expect(target).toBeVisible();
  await source.hover();
  expect(
    await source.evaluate((el) => {
      const r = el.getBoundingClientRect();
      return (
        document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === el
      );
    }),
  ).toBe(true);
  const s = await source.boundingBox(),
    t = await target.boundingBox();
  await page.mouse.move(s!.x + s!.width / 2, s!.y + s!.height / 2);
  await page.mouse.down();
  await page.mouse.move(t!.x + t!.width / 2, t!.y + t!.height / 2, {
    steps: 15,
  });
  await page.mouse.up();
  await expect(
    page.getByRole("heading", { name: "Nuovo Information Flow" }),
  ).toBeVisible();
  await page.getByLabel("Lead time del flusso").fill("30 min");
  await page.getByRole("button", { name: "Applica flusso" }).click();
  await expect
    .poll(
      async () =>
        (await getDoc()).entities.filter(
          (e: { type: string }) => e.type === "INFORMATION_FLOW",
        ).length,
    )
    .toBe(
      d.entities.filter((e: { type: string }) => e.type === "INFORMATION_FLOW")
        .length + 1,
    );
  const node = page.locator(`.react-flow__node[data-id="${a.id}"] strong`),
    box = await node.boundingBox();
  await page.mouse.move(box!.x + 30, box!.y + 5);
  await page.mouse.down();
  await page.mouse.move(box!.x + 110, box!.y + 25, { steps: 12 });
  await page.mouse.up();
  await expect
    .poll(
      async () =>
        (await getDoc()).entities.find((e: { id: string }) => e.id === a.id)
          .layout.x,
    )
    .not.toBe(a.layout.x);
  const before = (await getDoc()).viewport;
  await page.getByTitle("Pan", { exact: true }).click();
  const pane = await page.locator(".canvas-area").boundingBox();
  await page.mouse.move(pane!.x + pane!.width - 250, pane!.y + 30);
  await page.mouse.down();
  await page.mouse.move(pane!.x + pane!.width - 170, pane!.y + 60, {
    steps: 12,
  });
  await page.mouse.up();
  await expect.poll(async () => (await getDoc()).viewport.x).not.toBe(before.x);
  await page.locator(".react-flow__controls-zoomin").click();
  await expect
    .poll(async () => (await getDoc()).viewport.zoom)
    .toBeGreaterThan(before.zoom);
  expect(browserErrors).toEqual([]);
});

test("resize e collapse di un gruppo sopravvivono al reload", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page
    .locator(".library button")
    .filter({ hasText: "Process Group" })
    .click();
  await page.getByLabel("Nome elemento").fill("Gruppo ridimensionabile");
  await page.getByRole("button", { name: "Applica proprietà" }).click();
  await expect(page.locator(".heading-status")).toContainText("Salvato", {
    timeout: 10000,
  });
  const rid = await page.getByLabel("Revisione corrente").inputValue();
  const getGroup = async () => {
    const d = await (await request.get(`/api/revisions/${rid}`)).json();
    return d.entities.find(
      (e: { name: string }) => e.name === "Gruppo ridimensionabile",
    );
  };
  const before = await getGroup();
  await page.getByLabel("Cerca nel processo").fill("Gruppo ridimensionabile");
  await page
    .locator(".element-list")
    .getByRole("button", { name: "Gruppo ridimensionabile", exact: true })
    .click();
  await page.getByRole("button", { name: "Chiudi proprietà" }).click();
  const group = page.locator(`.react-flow__node[data-id="${before.id}"]`);
  const handle = group.locator(".react-flow__resize-control.bottom.right");
  await expect(handle).toBeVisible();
  await handle.hover();
  const box = await handle.boundingBox();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.down();
  await page.mouse.move(box!.x + 90, box!.y + 60, { steps: 15 });
  await page.mouse.up();
  await expect
    .poll(async () => (await getGroup()).layout.width)
    .toBeGreaterThan(before.layout.width);
  await group.locator("strong").dblclick();
  await expect.poll(async () => (await getGroup()).layout.collapsed).toBe(true);
  await page.reload();
  await page.getByLabel("Cerca nel processo").fill("Gruppo ridimensionabile");
  await page
    .locator(".element-list")
    .getByRole("button", { name: "Gruppo ridimensionabile", exact: true })
    .click();
  await expect(
    page.locator(`.react-flow__node[data-id="${before.id}"] .collapsed-node`),
  ).toBeVisible();
});

test("parametri configurati ricalcolano la policy senza alterare lo snapshot", async ({
  page,
  request,
}) => {
  const before = await (await request.get("/api/revisions/2")).json();
  await page.goto("/");
  await page.getByRole("button", { name: "Analisi", exact: true }).click();
  await page.getByRole("button", { name: "Stati & regole" }).click();
  const approval = page.locator("tr").filter({ hasText: "Approva PO" });
  await expect(approval).toContainText("REQUIRED");
  await page
    .getByLabel("MANAGEMENT_APPROVAL_THRESHOLD", { exact: true })
    .fill("750000");
  await page.getByRole("button", { name: "Applica parametri" }).click();
  await expect(approval).toContainText("OPTIONAL");
  await expect(page.locator(".heading-status")).toContainText("Salvato", {
    timeout: 10000,
  });
  await page.reload();
  await page.getByRole("button", { name: "Analisi", exact: true }).click();
  await page.getByRole("button", { name: "Stati & regole" }).click();
  await expect(
    page.locator("tr").filter({ hasText: "Approva PO" }),
  ).toContainText("OPTIONAL");
  expect(await (await request.get("/api/revisions/2")).json()).toEqual(before);
});
