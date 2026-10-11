import { test, expect } from "@playwright/test";

test("strumenti distinti, navigazione raccolta, pan e zoom non modificano elementi o lane", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.locator(".element-list summary")).toHaveCount(6);
  await expect(page.locator(".element-list button:visible")).toHaveCount(0);
  await page.getByLabel("Cerca nel processo").fill("Prepara RDA");
  await expect(page.locator(".element-list button:visible")).toHaveCount(2);
  await page
    .locator(".element-list")
    .getByRole("button", { name: "Prepara RDA", exact: true })
    .click();
  await page.getByRole("button", { name: "Chiudi proprietà" }).click();
  await expect(page.getByTitle("Seleziona", { exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(
    await page
      .locator(".react-flow__pane")
      .evaluate((e) => getComputedStyle(e).cursor),
  ).toBe("default");
  await page.getByLabel("Cerca nel processo").fill("");
  const rid = await page.getByLabel("Revisione corrente").inputValue();
  const document = async () =>
    (await request.get(`/api/revisions/${rid}`)).json();
  const before = await document();
  const node = before.entities.find(
    (e: { name: string }) => e.name === "Prepara RDA",
  );
  const layouts = (d: typeof before) =>
    d.entities.map((e: { id: string; layout: unknown }) => [e.id, e.layout]);
  await page.getByTitle("Pan", { exact: true }).click();
  await expect(page.getByTitle("Pan", { exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(
    await page
      .locator(".react-flow__pane")
      .evaluate((e) => getComputedStyle(e).cursor),
  ).toBe("grab");
  const box = await page
    .locator(`.react-flow__node[data-id="${node.id}"]`)
    .boundingBox();
  await page.mouse.move(box!.x + 40, box!.y + 30);
  await page.mouse.down();
  await page.mouse.move(box!.x + 150, box!.y + 90, { steps: 15 });
  await page.mouse.up();
  await expect
    .poll(async () => (await document()).viewport.x)
    .not.toBe(before.viewport.x);
  expect(layouts(await document())).toEqual(layouts(before));
  expect(await page.locator(".lane-node").count()).toBe(0);
  const zoomBefore = (await document()).viewport.zoom;
  await page.locator(".react-flow__controls-zoomin").click();
  await expect
    .poll(async () => (await document()).viewport.zoom)
    .toBeGreaterThan(zoomBefore);
  expect(layouts(await document())).toEqual(layouts(before));
  const bands = await page.locator(".lane-band").evaluateAll((es) =>
    es.map((e) => ({
      top: (e as HTMLElement).offsetTop,
      height: (e as HTMLElement).offsetHeight,
    })),
  );
  for (let i = 0; i < bands.length - 1; i++)
    expect(
      Math.abs(bands[i].top + bands[i].height - bands[i + 1].top),
    ).toBeLessThanOrEqual(1);
  const area = await page.locator(".canvas-area").boundingBox();
  expect(bands.at(-1)!.top + bands.at(-1)!.height).toBeGreaterThanOrEqual(
    area!.height - 1,
  );
  await page.getByTitle("Seleziona", { exact: true }).click();
  expect(
    await page
      .locator(".react-flow__pane")
      .evaluate((e) => getComputedStyle(e).cursor),
  ).toBe("default");
  await page.getByRole("button", { name: "100%", exact: true }).click();
  await expect.poll(async () => (await document()).viewport.zoom).toBe(1);
  expect(errors).toEqual([]);
});
