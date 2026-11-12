// SPDX-FileCopyrightText: 2026 Race Timing System contributors
// SPDX-License-Identifier: AGPL-3.0-or-later
// Placeholder until the client is generated from the server's OpenAPI schema (Phase 1).

export interface Health {
  status: string;
  database: string;
}

export function isHealth(value: unknown): value is Health {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Health).status === "string" &&
    typeof (value as Health).database === "string"
  );
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch("/api/health");
  if (!response.ok) throw new Error(`Health check failed: ${response.status}`);
  const body: unknown = await response.json();
  if (!isHealth(body)) throw new Error("Unexpected health response");
  return body;
}
