// Opt-in real-browser rehearsal; Python owns every synthetic row and API process.
const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");
const api = process.env.COUNSELCONNECT_TEST_API_URL;
assert.equal(new URL(api).hostname, "127.0.0.1", "Disposable loopback API required");
const studentId = Number(process.env.COUNSELCONNECT_TEST_STUDENT_ID);
const originalId = Number(process.env.COUNSELCONNECT_TEST_REQUEST_ID);
const mobile = process.env.COUNSELCONNECT_TEST_VIEWPORT === "mobile";
const artifacts = process.env.COUNSELCONNECT_TEST_ARTIFACTS;
const extended = process.env.COUNSELCONNECT_TEST_EXTENDED === "1";

async function main() {
  const { createServer } = await import("vite");
  const react = (await import("@vitejs/plugin-react")).default;
  const server = await createServer({ configFile: false, root: path.resolve(__dirname, ".."),
    plugins: [react()], server: { host: "127.0.0.1", port: 0,
      proxy: { "/api": { target: new URL(api).origin, ws: true } } } });
  let browser;
  try {
    await server.listen();
    const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
    browser = await chromium.launch({ channel: "chrome", headless: true });
    const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 } });
    // Keep synthetic test data on loopback; external fonts/icons are unnecessary.
    await context.route("**/*", route => {
      const url = new URL(route.request().url());
      return url.hostname === "127.0.0.1" || url.protocol === "blob:" || url.protocol === "data:"
        ? route.continue() : route.abort();
    });
    await context.addInitScript(() => {
      window.testRevokedUrls = [];
      const revoke = URL.revokeObjectURL.bind(URL);
      URL.revokeObjectURL = url => { window.testRevokedUrls.push(url); revoke(url); };
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    page.setDefaultTimeout(15000);
    async function signIn(identifier, password, staff) {
      await context.clearCookies();
      await page.goto(`${origin}/#${staff ? "staff-login" : "login"}`);
      await page.locator("#identifier").fill(identifier);
      await page.locator("#password").fill(password);
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await page.waitForURL("**/#home");
    }
    async function navigate(hash) {
      const nav = page.getByRole("navigation", { name: "App navigation", exact: true });
      if (mobile) await nav.getByRole("button", { name: /menu/i }).click();
      await (mobile ? page.locator("#app-nav-links") : nav).locator(`a[href="#${hash}"]:visible`).click();
      await page.waitForURL(`**/#${hash}`);
    }
    async function preview(id) {
      await page.locator(`#review-open-${id}`).click();
      const responsePromise = page.waitForResponse(response => response.url().endsWith(`/profile-change-requests/${id}/cor`));
      await page.getByRole("button", { name: "Preview current COR", exact: true }).click();
      const response = await responsePromise;
      assert.equal(response.status(), 200);
      assert.match(response.headers()["cache-control"], /no-store/);
      assert.match(response.headers()["content-type"], /application\/pdf/);
      const frame = page.locator('iframe[title="Current correction COR"]');
      await frame.waitFor();
      assert.match(await frame.getAttribute("src"), /^blob:/);
      return frame.getAttribute("src");
    }
    await signIn(process.env.COUNSELCONNECT_TEST_MANAGER, "synthetic-ui-pass", true);
    await navigate("users");
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.locator(`#user-open-${studentId}`).waitFor();
    await page.getByLabel("Search users", { exact: true }).fill(process.env.COUNSELCONNECT_TEST_STUDENT);
    await page.locator(`#user-open-${studentId}`).click();
    await page.locator(`#user-status-${studentId}`).waitFor();
    if (artifacts) await page.screenshot({ path: path.join(artifacts, "users.png"), fullPage: true });
    await navigate("corrections");
    const firstBlob = await preview(originalId);
    if (extended && artifacts) await page.screenshot({ path: path.join(artifacts, "valid-pdf-preview.png"), fullPage: true });
    await page.getByRole("button", { name: "Close preview", exact: true }).click();
    await page.waitForFunction(url => window.testRevokedUrls.includes(url), firstBlob);
    const secondBlob = await (async () => {
      await page.getByRole("button", { name: "Preview current COR", exact: true }).click();
      const frame = page.locator('iframe[title="Current correction COR"]');
      await frame.waitFor(); return frame.getAttribute("src");
    })();
    await navigate("users");
    await page.waitForFunction(url => window.testRevokedUrls.includes(url), secondBlob);
    await navigate("corrections");
    await page.locator(`#review-open-${originalId}`).click();
    let stalePage;
    if (extended) {
      stalePage = await context.newPage();
      await stalePage.goto(`${origin}/#corrections`);
      await stalePage.locator(`#review-open-${originalId}`).click();
      await stalePage.locator(`#review-return-${originalId}`).click();
      await stalePage.getByLabel("Return reason", { exact: true }).fill("Stale second reviewer decision.");
    }
    await page.locator(`#review-return-${originalId}`).click();
    await page.getByLabel("Return reason", { exact: true }).fill("Check section on the synthetic COR.");
    await page.locator("#confirm-correction-decision").click();
    await page.getByText("Return reason: Check section on the synthetic COR.", { exact: true }).waitFor();
    if (stalePage) {
      const conflict = stalePage.waitForResponse(response => response.url().endsWith(`/${originalId}/return`) && response.request().method() === "POST");
      await stalePage.locator("#confirm-correction-decision").click();
      assert.equal((await conflict).status(), 409);
      await stalePage.getByText(/Reload the current request before another decision/).waitFor();
      await stalePage.waitForFunction(id => document.getElementById(`review-return-${id}`)?.disabled, originalId);
      await stalePage.close();
    }

    await signIn(process.env.COUNSELCONNECT_TEST_STUDENT, "password1", false);
    // Registration remains available to ACTIVE Students in the app navigation.
    await page.goto(`${origin}/#registration`);
    await page.locator(`#my-correction-${originalId}`).click();
    await page.getByLabel("Section", { exact: true }).fill("B");
    await page.getByLabel("Fresh current COR PDF", { exact: true }).setInputFiles({ name: "fresh.pdf", mimeType: "application/pdf", buffer: process.env.COUNSELCONNECT_TEST_PDF_BASE64 ? Buffer.from(process.env.COUNSELCONNECT_TEST_PDF_BASE64, "base64") : Buffer.from("%PDF-1.4 synthetic fresh browser proof") });
    const revisionResponse = page.waitForResponse(response => response.url().endsWith(`/${originalId}/resubmit`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "Submit correction revision", exact: true }).click();
    const created = await revisionResponse;
    assert.equal(created.status(), 201);
    const revision = (await created.json()).change_request;
    assert.equal(revision.previous_change_request_id, originalId);
    assert.equal(revision.submission_version, 2);
    await page.locator(`#my-correction-${revision.change_request_id}`).waitFor();
    if (artifacts) await page.screenshot({ path: path.join(artifacts, "student-revision.png"), fullPage: true });
    const studentCookies = extended ? await context.cookies() : null;

    await signIn(process.env.COUNSELCONNECT_TEST_MANAGER, "synthetic-ui-pass", true);
    await navigate("corrections");
    const approvalBlob = await preview(revision.change_request_id);
    await page.locator(`#review-approve-${revision.change_request_id}`).click();
    await page.locator("#confirm-correction-decision").click();
    await page.getByText("Corrections approved.", { exact: true }).waitFor();
    await page.waitForFunction(url => window.testRevokedUrls.includes(url), approvalBlob);
    await navigate("users");
    await page.getByLabel("Search users", { exact: true }).fill(process.env.COUNSELCONNECT_TEST_STUDENT);
    await page.locator(`#user-open-${studentId}`).click();
    await page.locator(`#user-status-${studentId}`).click();
    assert.ok((await page.locator("fieldset").innerText()).includes(process.env.COUNSELCONNECT_TEST_STUDENT));
    await page.locator("#confirm-user-status").click();
    await page.getByRole("button", { name: "Reactivate account", exact: true }).waitFor();
    let revokedContext;
    if (extended) {
      revokedContext = await browser.newContext();
      await revokedContext.addCookies(studentCookies);
      assert.ok([401, 403].includes((await revokedContext.request.get(`${origin}/api/v1/auth/me`)).status()));
    }
    await page.locator(`#user-status-${studentId}`).click();
    await page.locator("#confirm-user-status").click();
    await page.getByRole("button", { name: "Deactivate account", exact: true }).waitFor();
    if (revokedContext) {
      assert.ok([401, 403].includes((await revokedContext.request.get(`${origin}/api/v1/auth/me`)).status()));
      await revokedContext.close();
      await signIn(process.env.COUNSELCONNECT_TEST_STUDENT, "password1", false);
      if (mobile) {
        await page.getByRole("button", { name: "Open menu", exact: true }).click();
        await page.locator('#app-nav-links a[href="#registration"]').click();
      } else {
        await page.locator('a[href="#registration"]:visible').click();
      }
      await page.locator(`#my-correction-${revision.change_request_id}`).click();
      await page.getByText("Your registered information now reflects the approved changes.", { exact: true }).waitFor();
    }
    assert.deepEqual(errors, [], "Browser must have no uncaught application errors");
    console.log(`Real Chrome management flow passed (${mobile ? "390x844" : "1440x1000"}): navigation, paging, search, preview cleanup, return, fresh revision, approval and status confirmations.`);
  } finally {
    if (browser) await browser.close();
    await server.close();
  }
}
main().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
