"use client";

import { useEffect, useState } from "react";

import { ApiRequestError, fetchHealth } from "../lib/api";

type HealthState =
  | { status: "loading" }
  | { status: "ok" }
  | { status: "error"; message: string };

export function HealthPill() {
  const [state, setState] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        await fetchHealth();
        if (!cancelled) {
          setState({ status: "ok" });
        }
      } catch (error) {
        if (!cancelled) {
          const message =
            error instanceof ApiRequestError
              ? error.message
              : "Unable to reach API from this frontend origin.";
          setState({ status: "error", message });
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") {
    return <span className="health-pill is-loading">Checking API link...</span>;
  }

  if (state.status === "ok") {
    return <span className="health-pill is-ok">API connected</span>;
  }

  return (
    <span className="health-pill is-error" title={state.message}>
      API unreachable
    </span>
  );
}
