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
  // Vite treats port 0 as its default 5173. Reserve an ephemeral port so
  // rehearsal never competes with the user's running development frontend.
  const listener = require("node:net").createServer();
  await new Promise((resolve, reject) => { listener.once("error", reject); listener.listen(0, "127.0.0.1", resolve); });
  const frontendPort = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  const { createServer } = await import("vite");
  const react = (await import("@vitejs/plugin-react")).default;
  const server = await createServer({ configFile: false, root: path.resolve(__dirname, ".."),
    plugins: [react()], server: { host: "127.0.0.1", port: frontendPort, strictPort: true,
      proxy: { "/api": { target: new URL(api).origin, ws: true } } } });
  let browser, page;
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
    page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("requestfailed", request => {
      const url = new URL(request.url());
      if (url.hostname === "127.0.0.1" && url.pathname.startsWith("/api/")) console.error("Loopback request failed:", url.pathname, request.failure()?.errorText);
    });
    page.setDefaultTimeout(15000);
    async function signIn(identifier, password, staff) {
      await context.clearCookies();
      await page.goto(`${origin}/#${staff ? "superadmin-login" : "login"}`);
      await page.locator("#identifier").fill(identifier);
      await page.locator("#password").fill(password);
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await page.waitForURL("**/#home");
    }
    async function navigate(hash) {
      const dialog = page.getByRole("dialog");
      if (await dialog.count()) await dialog.getByRole("button", { name: /^Close (user details|correction review|student details)$/i }).click();
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
    if (process.env.COUNSELCONNECT_TEST_COUNSELORS === "1") {
      await signIn(process.env.COUNSELCONNECT_TEST_MANAGER, "synthetic-ui-pass", true);
      await navigate("users");
      await page.getByRole("button", { name: "Create Counselor", exact: true }).click();
      let dialog = page.getByRole("dialog", { name: "Create Counselor", exact: true });
      await dialog.getByLabel("First name", { exact: true }).fill("Browser");
      await dialog.getByLabel("Middle name (optional)", { exact: true }).fill("Reyes");
      await dialog.getByLabel("Last name", { exact: true }).fill("Counselor");
      const email = `browser-counselor-${studentId}@example.edu`;
      await dialog.getByLabel("Email", { exact: true }).fill(email);
      await dialog.getByLabel("Initial password", { exact: true }).fill("browser-initial-password");
      await dialog.getByLabel("Confirm password", { exact: true }).fill("browser-initial-password");
      if (artifacts) await page.screenshot({ path: path.join(artifacts, "create-counselor.png"), fullPage: true });
      const createdResponse = page.waitForResponse(response => response.url().endsWith("/accounts/users") && response.request().method() === "POST");
      await dialog.getByRole("button", { name: "Create Counselor", exact: true }).click();
      const response = await createdResponse;
      assert.equal(response.status(), 201);
      assert.match(response.headers()["cache-control"], /no-store/);
      const created = await response.json();
      assert.equal(created.role_code, "COUNSELOR");
      assert.equal(created.account_status, "ACTIVE");
      assert.equal(created.is_deactivated, false);
      assert.equal(created.password_hash, undefined);
      assert.equal(created.password, undefined);
      await page.locator(`#counselor-edit-${created.user_id}`).waitFor();
      const counselorContext = await browser.newContext();
      try {
        const login = await counselorContext.request.post(`${origin}/api/v1/auth/login`, { data: { identifier: email, password: "browser-initial-password" } });
        assert.equal(login.status(), 200);
        assert.equal((await login.json()).user.role_code, "COUNSELOR");
        await page.locator(`#counselor-edit-${created.user_id}`).click();
        dialog = page.getByRole("dialog", { name: "Edit Counselor", exact: true });
        const changedEmail = `edited-counselor-${created.user_id}@example.edu`;
        await dialog.getByLabel("Email", { exact: true }).fill(changedEmail);
        await dialog.getByLabel("First name", { exact: true }).fill("Updated");
        const updateResponse = page.waitForResponse(response => response.url().endsWith(`/accounts/users/${created.user_id}`) && response.request().method() === "PATCH");
        await dialog.getByRole("button", { name: "Save Counselor changes", exact: true }).click();
        const updated = await updateResponse;
        assert.equal(updated.status(), 200);
        const account = await updated.json();
        assert.equal(account.user_id, created.user_id);
        assert.equal(account.email, changedEmail);
        assert.equal(account.first_name, "Updated");
        await page.locator(`#counselor-edit-${created.user_id}`).waitFor();
        if (artifacts) await page.screenshot({ path: path.join(artifacts, "updated-counselor.png"), fullPage: true });
        assert.ok([401, 403].includes((await counselorContext.request.get(`${origin}/api/v1/auth/me`)).status()));
        assert.equal((await counselorContext.request.post(`${origin}/api/v1/auth/login`, { data: { identifier: email, password: "browser-initial-password" } })).status(), 401);
        assert.equal((await counselorContext.request.post(`${origin}/api/v1/auth/login`, { data: { identifier: changedEmail, password: "browser-initial-password" } })).status(), 200);
      } finally { await counselorContext.close(); }
      assert.deepEqual(errors, []);
      console.log(`Counselor creation/edit/browser flow passed (${mobile ? "mobile" : "desktop"}).`);
      return;
    }
    await signIn(process.env.COUNSELCONNECT_TEST_MANAGER, "synthetic-ui-pass", true);
    await navigate("student-directory");
    await page.getByRole("heading", { name: "Student Directory", exact: true }).waitFor();
    await page.getByLabel("Search users", { exact: true }).fill(process.env.COUNSELCONNECT_TEST_STUDENT);
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await page.getByRole("button", { name: "View", exact: true }).click();
    await page.getByRole("dialog", { name: "Student details", exact: true }).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "Recovery table scrolling must not widen the page");
    if (artifacts) await page.screenshot({ path: path.join(artifacts, "recovery-details.png"), fullPage: true });
    await page.keyboard.press("Escape");
    await page.getByRole("dialog").waitFor({ state: "detached" });
    await navigate("users");
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.locator(`#user-open-${studentId}`).waitFor();
    await page.getByLabel("Search users", { exact: true }).fill(process.env.COUNSELCONNECT_TEST_STUDENT);
    await page.locator(`#user-open-${studentId}`).waitFor();
    if (artifacts) await page.screenshot({ path: path.join(artifacts, "users-list.png"), fullPage: true });
    await page.locator(`#user-open-${studentId}`).click();
    await page.locator(`#user-status-${studentId}`).waitFor();
    assert.equal(await page.evaluate(() => document.body.style.overflow), "hidden");
    const userDialog = page.getByRole("dialog", { name: "User details", exact: true });
    assert.ok(await userDialog.evaluate(node => node.contains(document.activeElement)), "Focus enters the dialog");
    await userDialog.getByRole("button", { name: "Close user details", exact: true }).focus();
    await page.keyboard.press("Shift+Tab");
    assert.ok(await userDialog.evaluate(node => node.contains(document.activeElement)), "Tab stays within the dialog");
    if (artifacts) await page.screenshot({ path: path.join(artifacts, "users.png"), fullPage: true });
    await page.keyboard.press("Escape");
    await page.getByRole("dialog").waitFor({ state: "detached" });
    assert.equal(await page.locator(`#user-open-${studentId}`).evaluate(node => node === document.activeElement), true, "Closing restores focus to the selected account");
    assert.equal(await page.evaluate(() => document.body.style.overflow), "");
    await navigate("corrections");
    await page.locator(`#review-open-${originalId}`).waitFor();
    if (artifacts) await page.screenshot({ path: path.join(artifacts, "corrections-list.png"), fullPage: true });
    const firstBlob = await preview(originalId);
    assert.ok(await page.getByRole("dialog", { name: "Correction review", exact: true }).evaluate(node => {
      const box = node.querySelector(".superadmin-dialog").getBoundingClientRect();
      return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight;
    }), "Review dialog fits the viewport");
    if (extended && artifacts) await page.screenshot({ path: path.join(artifacts, "valid-pdf-preview.png"), fullPage: true });
    await page.getByRole("button", { name: "Close preview", exact: true }).click();
    await page.waitForFunction(url => window.testRevokedUrls.includes(url), firstBlob);
    const secondBlob = await (async () => {
      await page.getByRole("button", { name: "Preview current COR", exact: true }).click();
      const frame = page.locator('iframe[title="Current correction COR"]');
      await frame.waitFor(); return frame.getAttribute("src");
    })();
    // Browser hash navigation while preview is open must still release the URL.
    await page.evaluate(() => { window.location.hash = "#users"; });
    await page.waitForURL("**/#users");
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
  } catch (error) {
    if (page && artifacts) await page.screenshot({ path: path.join(artifacts, "failure.png"), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    if (browser) await browser.close();
    await server.close();
  }
}
main().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
