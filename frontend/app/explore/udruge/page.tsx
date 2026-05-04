"use client";

import { useEffect, useState, useCallback } from "react";
import Header from "../../components/Header";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Udruga = {
  id: string;
  naziv: string;
  skraceni_naziv: string | null;
  oib: string | null;
  zupanija: string | null;
  adresa: string | null;
  datum_osnivanja: string | null;
  djelatnosti: Record<string, string> | null;
};

type ApiResponse = {
  total: number;
  limit: number;
  offset: number;
  results: Udruga[];
};

export default function UdrugePage() {
  const [naziv, setNaziv] = useState("");
  const [zupanija, setZupanija] = useState("");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const LIMIT = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({
      limit: LIMIT.toString(),
      offset: (page * LIMIT).toString(),
    });
    if (naziv) params.set("naziv", naziv);
    if (zupanija) params.set("zupanija", zupanija);

    try {
      const res = await fetch(`${API}/api/udruge?${params}`);
      setData(await res.json());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [naziv, zupanija, page]);

  useEffect(() => {
    const t = setTimeout(fetchData, 300);
    return () => clearTimeout(t);
  }, [fetchData]);

  useEffect(() => { setPage(0); }, [naziv, zupanija]);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const z = p.get("zupanija");
    if (z) setZupanija(z);
  }, []);

  const totalPages = data ? Math.ceil(data.total / LIMIT) : 0;

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Header
        title="Registar udruga"
        subtitle={data ? `${data.total.toLocaleString()} rezultata` : "…"}
        activePath="/explore/udruge"
      />

      <div className="max-w-6xl mx-auto px-6 py-6 space-y-4">
        <div className="flex gap-3 flex-wrap">
          <input
            type="text"
            placeholder="Pretraži po nazivu…"
            value={naziv}
            onChange={(e) => setNaziv(e.target.value)}
            className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm w-72 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="text"
            placeholder="Županija…"
            value={zupanija}
            onChange={(e) => setZupanija(e.target.value)}
            className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm w-52 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {(naziv || zupanija) && (
            <button
              onClick={() => { setNaziv(""); setZupanija(""); }}
              className="text-sm text-gray-500 hover:text-red-500 px-2"
            >
              Obriši filtere
            </button>
          )}
        </div>

        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-sm text-gray-400">Učitavam…</div>
          ) : !data || data.results.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400">Nema rezultata.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2 text-left">Naziv</th>
                  <th className="px-4 py-2 text-left">OIB</th>
                  <th className="px-4 py-2 text-left">Županija</th>
                  <th className="px-4 py-2 text-left">Sjedište</th>
                  <th className="px-4 py-2 text-left">Datum osnivanja</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {data.results.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="px-4 py-2 font-medium text-gray-900 dark:text-gray-100 max-w-xs">
                      <span title={u.naziv ?? ""}>{u.naziv ?? "—"}</span>
                      {u.skraceni_naziv && (
                        <span className="ml-1 text-xs text-gray-400">({u.skraceni_naziv})</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400 font-mono text-xs">{u.oib ?? "—"}</td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{u.zupanija ?? "—"}</td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400 max-w-xs truncate">{u.adresa ?? "—"}</td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400">
                      {u.datum_osnivanja ? new Date(u.datum_osnivanja).toLocaleDateString("hr-HR") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between text-sm text-gray-600 dark:text-gray-400">
            <span>Stranica {page + 1} od {totalPages.toLocaleString()}</span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1 border border-gray-200 dark:border-gray-600 rounded-lg disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                ← Prethodno
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1 border border-gray-200 dark:border-gray-600 rounded-lg disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                Sljedeće →
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
