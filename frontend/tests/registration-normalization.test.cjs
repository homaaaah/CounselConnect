const assert = require("node:assert/strict");
const { test } = require("node:test");
require("./register-app.cjs");
const { editedEditableFields } = require("../src/features/accounts/useRegistration.js");
const { YEAR_LEVELS } = require("../src/features/accounts/ScreeningFields.jsx");
const cases = require("../../contracts/registration-normalization-cases.json");
const base = { first_name: "Ana", middle_name: null, last_name: "Cruz", year_level: 1, section: "A" };

for (const example of cases) {
  test(`correction preview: ${example.field} ${JSON.stringify(example.proposed)}`, () => {
    const extracted = { ...base, [example.field]: example.extracted };
    const screening = Object.fromEntries(Object.entries(extracted).map(([key, value]) => [`extracted_${key}`, value]));
    const form = { ...extracted, [example.field]: example.proposed };
    const expected = example.preview_changed ?? example.changed;
    assert.deepEqual(editedEditableFields(screening, form), expected ? [example.field] : []);
  });
}

test("year selector supports the backend's full allowed range", () => {
  assert.deepEqual(YEAR_LEVELS, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
});
