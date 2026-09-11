/**
 * API transport layer.
 *
 * - apiClient.js: fetch wrapper that PRESERVES snake_case DTO fields
 *   (no silent global case conversion — NAMING_CONVENTIONS.md).
 * - Domain service files (auth.js, accounts.js, ...) map 1:1 to backend
 *   modules and must stay consistent with contracts/openapi.json.
 */
export {};
