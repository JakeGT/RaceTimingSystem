// SPDX-FileCopyrightText: 2026 Race Timing System contributors
// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { isHealth } from "./api";

describe("isHealth", () => {
  it("accepts a valid health payload", () => {
    expect(isHealth({ status: "ok", database: "sqlite" })).toBe(true);
  });

  it("rejects anything else", () => {
    expect(isHealth(null)).toBe(false);
    expect(isHealth({ status: "ok" })).toBe(false);
  });
});
