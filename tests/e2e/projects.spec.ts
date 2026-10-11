import { test, expect } from "@playwright/test";
test("progetto vuoto, icone, regole e template gruppo persistono e non modificano il demo", async ({
  page,
  request,
}) => {
  const demo = await (await request.get("/api/revisions/2")).json();
  await page.goto("/");
  await page.getByRole("button", { name: "Progetti", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Libreria progetti" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Nuovo progetto", exact: true })
    .click();
  await page
    .getByLabel("Nome progetto", { exact: true })
    .fill("Progetto qualità — è nuovo");
  await page
    .getByLabel("Nome processo", { exact: true })
    .fill("Processo vuoto browser");
  await page
    .getByRole("button", { name: "Crea progetto vuoto", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Processo vuoto browser", exact: true }),
  ).toBeVisible();
  const rid = await page.getByLabel("Revisione corrente").inputValue();
  let doc = await (await request.get(`/api/revisions/${rid}`)).json();
  expect(doc.entities).toEqual([]);
  expect(doc.relations).toEqual([]);
  expect(doc.rules).toEqual([]);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Processo vuoto browser", exact: true }),
  ).toBeVisible();
  await page
    .locator(".library")
    .getByRole("button", { name: "Action", exact: true })
    .click();
  await page.getByLabel("Nome elemento").fill("Controlla qualità");
  await page.getByRole("button", { name: "Applica proprietà" }).click();
  await page.getByRole("button", { name: "Chiudi proprietà" }).click();
  await page.getByRole("button", { name: /^Regole/ }).click();
  await page.getByRole("button", { name: "Nuova regola", exact: true }).click();
  await page.getByLabel("Nome regola").fill("Controllo sempre richiesto");
  await page.getByRole("button", { name: "Salva regola", exact: true }).click();
  await expect(page.locator(".rule-cards")).toContainText(
    "Controllo sempre richiesto",
  );
  await page
    .locator(".rule-cards")
    .getByRole("button", { name: "Modifica", exact: true })
    .click();
  await page.getByLabel("Nome regola").fill("Controllo aggiornato");
  await page.getByLabel("Se vero", { exact: true }).selectOption("FORBIDDEN");
  await page.getByRole("button", { name: "Salva regola", exact: true }).click();
  await expect(page.locator(".rule-cards")).toContainText("FORBIDDEN");
  await page.getByTitle("Chiudi gestione regole").click();
  await page
    .getByRole("button", { name: "Mezzi e icone", exact: true })
    .click();
  await page
    .locator(".sidebar .means-icon-picker")
    .getByRole("button", { name: "Telefono", exact: true })
    .click();
  await expect(page.getByRole("group", { name: "Icona mezzo" })).toBeVisible();
  await page.getByTitle("Icona Teams", { exact: true }).click();
  await page.getByRole("button", { name: "Applica proprietà" }).click();
  await page.getByRole("button", { name: "Chiudi proprietà" }).click();
  await page
    .getByRole("button", { name: "Mezzi e icone", exact: true })
    .click();
  await page
    .locator(".library")
    .getByRole("button", { name: "Process Group", exact: true })
    .click();
  await page.getByLabel("Nome elemento").fill("Gruppo riutilizzabile");
  await page.getByRole("button", { name: "Applica proprietà" }).click();
  await page.getByRole("button", { name: "Chiudi proprietà" }).click();
  await page
    .getByRole("button", { name: "Libreria gruppi", exact: true })
    .click();
  await page.getByLabel("Nome template gruppo").fill("Template qualità");
  await page
    .getByRole("button", { name: "Salva nella libreria", exact: true })
    .click();
  await expect(page.locator(".project-cards")).toContainText(
    "Template qualità",
  );
  await page
    .getByRole("button", { name: "Inserisci gruppo", exact: true })
    .click();
  await page.getByRole("button", { name: "Salva", exact: true }).click();
  await expect
    .poll(
      async () =>
        (
          await (await request.get(`/api/revisions/${rid}`)).json()
        ).entities.filter((e: { type: string }) => e.type === "PROCESS_GROUP")
          .length,
    )
    .toBe(2);
  await page.reload();
  doc = await (await request.get(`/api/revisions/${rid}`)).json();
  expect(doc.rules[0].name).toBe("Controllo aggiornato");
  expect(
    doc.entities.find((e: { type: string }) => e.type === "MEANS").properties
      .MEANS_ICON,
  ).toBe("Teams");
  expect(await (await request.get("/api/revisions/2")).json()).toEqual(demo);
  await page.getByRole("button", { name: "Progetti", exact: true }).click();
  await page.getByLabel("Cerca progetti").fill("Progetto qualità");
  await expect(page.locator(".project-cards article")).toHaveCount(1);
});
