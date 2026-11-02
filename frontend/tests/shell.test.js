import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const cssSource = await readFile(new URL("../src/index.css", import.meta.url), "utf8");

test("global shell renders persistent match context and change action", () => {
  assert.match(appSource, /data-testid="match-context-bar"/);
  assert.match(appSource, /Selected match/);
  assert.match(appSource, /Demo fixture · not live/);
  assert.match(appSource, /Change match/);
});

test("global shell uses non-wrapping responsive navigation and visible focus styles", () => {
  assert.match(cssSource, /\.shell-nav-wrap\s*\{[\s\S]*overflow-x: auto/);
  assert.match(cssSource, /\.shell-tab\s*\{[\s\S]*white-space: nowrap/);
  assert.match(cssSource, /button:focus-visible/);
});

test("shared visual primitives expose consistent component APIs", async () => {
  const uiSource = await readFile(new URL("../src/components/ui.jsx", import.meta.url), "utf8");
  assert.match(uiSource, /export function Panel/);
  assert.match(uiSource, /export function MetricCard/);
  assert.match(uiSource, /export function StatusBadge/);
  assert.match(uiSource, /export function PageHeader/);
  assert.match(uiSource, /export function LoadingState/);
  assert.match(uiSource, /export function EmptyState/);
  assert.match(uiSource, /export function ErrorState/);
  assert.match(uiSource, /role="alert"/);
  assert.match(uiSource, /aria-live="polite"/);
});
