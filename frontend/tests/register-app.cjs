const fs = require("node:fs");

// Load actual app modules for Node tests; supply Vite's environment
// without changing any application behavior or replacing app functions.
// The frontend is plain JavaScript (JS/JSX); Vite's bundled esbuild
// compiles the ESM sources to CJS for Node and transforms JSX.
const environment = JSON.stringify({ VITE_API_BASE_URL: process.env.COUNSELCONNECT_TEST_API_URL });
const { transformSync } = require("esbuild");
for (const extension of [".js", ".jsx"]) {
  require.extensions[extension] = (module, filename) => {
    const source = fs.readFileSync(filename, "utf8").replaceAll("import.meta.env", `(${environment})`);
    const { code } = transformSync(source, {
      format: "cjs",
      target: "es2022",
      loader: extension === ".jsx" ? "jsx" : "js",
      jsx: "automatic",
      sourcemap: false,
    });
    module._compile(code, filename);
  };
}

// Node falls back to the `.js` handler for unknown extensions, so image
// imports (appointment.jpg, bg.jpg, ...) would be parsed as JavaScript.
// Stub them with the asset path, mirroring what Vite returns for asset
// imports in dev builds.
for (const assetExtension of [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]) {
  require.extensions[assetExtension] = (module, filename) => {
    module._compile(`module.exports = ${JSON.stringify(filename)};`, filename);
  };
}
