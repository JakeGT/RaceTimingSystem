// SPDX-FileCopyrightText: 2026 Race Timing System contributors
// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";
import { fetchHealth, type Health } from "./api";

export function App() {
  const [health, setHealth] = useState<Health | "error" | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth("error"));
  }, []);

  return (
    <main>
      <h1>Race Timing</h1>
      <p>
        Server:{" "}
        {health === null
          ? "checking…"
          : health === "error"
            ? "unreachable"
            : `${health.status} (${health.database})`}
      </p>
    </main>
  );
}
