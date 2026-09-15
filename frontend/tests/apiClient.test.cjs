const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const { transformSync } = require("esbuild");

for (const [configured, expected] of [
  [undefined, "/api/v1"],
  ["", "/api/v1"],
  [" /api/v1/ ", "/api/v1"],
  ["https://api.example.test/api/v1/", "https://api.example.test/api/v1"],
]) {
  test(`API requests use normalized base ${JSON.stringify(configured)}`, async () => {
    const source = fs.readFileSync(require.resolve("../src/services/apiClient.js"), "utf8")
      .replaceAll("import.meta.env", JSON.stringify({ VITE_API_BASE_URL: configured }));
    const { code } = transformSync(source, { format: "cjs" });
    const calls = [];
    const context = { module: { exports: {} }, FormData, fetch: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ status: "ok" }));
    } };
    vm.runInNewContext(code, context);
    await context.module.exports.request("/health");
    assert.equal(calls[0].url, `${expected}/health`);
    assert.equal(calls[0].init.credentials, "include");
    assert.equal(context.module.exports.API_BASE_URL, expected);
  });
}
