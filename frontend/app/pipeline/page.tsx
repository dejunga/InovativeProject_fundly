"use client";

import { useEffect, useState } from "react";
import Header from "../components/Header";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Run = {
  id: string;
  run_type: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  datasets_checked: number;
  datasets_changed: number;
  datasets_unchanged: number;
  rows_inserted: number;
  rows_updated: number;
  rows_soft_deleted: number;
  error_message: string | null;
};

const statusColor: Record<string, string> = {
  success: "text-green-600 bg-green-50 dark:bg-green-900/30",
  partial: "text-yellow-600 bg-yellow-50 dark:bg-yellow-900/30",
  failed: "text-red-600 bg-red-50 dark:bg-red-900/30",
};

function duration(start: string, end: string | null): string {
  if (!end) return "running…";
  const s = (new Date(end).getTime() - new Date(start).getTime()) / 1000;
  if (s < 60) return `${s.toFixed(0)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export default function PipelinePage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState("");

  const load = async () => {
    try {
      const res = await fetch(`${API}/api/pipeline/runs?limit=20`);
      setRuns(await res.json());
    } catch {
      setRuns([]);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 10_000);
    return () => clearInterval(interval);
  }, []);

  const triggerRun = async () => {
    setTriggering(true);
    setTriggerMsg("");
    try {
      const res = await fetch(`${API}/api/pipeline/run`, { method: "POST" });
      const data = await res.json();
      setTriggerMsg(data.message);
      setTimeout(load, 2000);
    } catch {
      setTriggerMsg("Greška pri pokretanju.");
    } finally {
      setTriggering(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Header title="Pipeline runs" subtitle="Historija ETL izvršavanja" activePath="/pipeline" />

      <div className="max-w-5xl mx-auto px-6 py-6 space-y-4">
        <div className="flex items-center gap-4">
          <button
            onClick={triggerRun}
            disabled={triggering}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {triggering ? "Pokrećem…" : "Pokreni pipeline"}
          </button>
          {triggerMsg && <span className="text-sm text-gray-600 dark:text-gray-400">{triggerMsg}</span>}
          <button onClick={load} className="ml-auto text-sm text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400">
            Osvježi
          </button>
        </div>

        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          {runs.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400">Nema runova.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2 text-left">Vrsta</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">Pokrenuto</th>
                  <th className="px-4 py-2 text-right">Trajanje</th>
                  <th className="px-4 py-2 text-right">Datasets</th>
                  <th className="px-4 py-2 text-right">Rows ins.</th>
                  <th className="px-4 py-2 text-right">Rows upd.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-gray-700" title={r.error_message ?? ""}>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400 capitalize">{r.run_type}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusColor[r.status] ?? "text-gray-500 bg-gray-100"}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400">
                      {new Date(r.started_at).toLocaleString("hr-HR")}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                      {duration(r.started_at, r.finished_at)}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                      {r.datasets_checked} / {r.datasets_changed} changed
                    </td>
                    <td className="px-4 py-2 text-right text-green-600 font-medium">{r.rows_inserted.toLocaleString()}</td>
                    <td className="px-4 py-2 text-right text-blue-600 font-medium">{r.rows_updated.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </main>
  );
}
