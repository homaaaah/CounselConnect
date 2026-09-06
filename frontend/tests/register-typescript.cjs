const fs = require("node:fs");
const ts = require("typescript");

// Compile actual app modules for Node tests; supply Vite's environment
// without changing any application behavior or replacing app functions.
const environment = JSON.stringify({ VITE_API_BASE_URL: process.env.COUNSELCONNECT_TEST_API_URL });
for (const extension of [".ts", ".tsx"]) {
  require.extensions[extension] = (module, filename) => {
    const source = fs.readFileSync(filename, "utf8").replaceAll("import.meta.env", `(${environment})`);
    module._compile(ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    }).outputText, filename);
  };
}
