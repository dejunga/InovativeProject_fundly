"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Header from "../components/Header";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Potpora = {
  id: string;
  oib: string | null;
  organizacija: string;
  projekt: string | null;
  davatelj: string | null;
  razina: string;
  zupanija_provedbe: string | null;
  godina: number | null;
  iznos: number | null;
};

type ApiResponse = { total: number; results: Potpora[] };

type Statistike = {
  ukupno: { broj_potpora: number; ukupni_iznos: number };
  po_razini: { razina: string; broj: number; ukupno: number }[];
};

type DavateljRow = { davatelj: string; broj: number; ukupno: number };
type OrgRow = { organizacija: string; oib: string | null; ukupno: number };

const RAZINA_LABELS: Record<string, string> = {
  drzava: "Država", zupanija: "Županija", grad: "Grad", opcina: "Općina",
};
const RAZINA_COLORS: Record<string, string> = {
  drzava: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  zupanija: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  grad: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  opcina: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
};

function fmt(n: number | null): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("hr-HR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
}

// ── Multi-select searchable dropdown ─────────────────────────────────────────
function MultiSelect({
  label,
  values,
  onChange,
  options,
}: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
  options: { value: string; label: string; sub?: string }[];
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = options
    .filter((o) => o.label.toLowerCase().includes(search.toLowerCase()))
    .slice(0, 150);

  const toggle = (val: string) => {
    onChange(values.includes(val) ? values.filter((v) => v !== val) : [...values, val]);
  };

  const buttonLabel =
    values.length === 0
      ? label
      : values.length === 1
      ? (options.find((o) => o.value === values[0])?.label ?? values[0])
      : `${values.length} odabrano`;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center justify-between gap-2 w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-800 text-left
          ${values.length > 0 ? "border-blue-500 dark:border-blue-400" : "border-gray-300 dark:border-gray-600"}
          text-gray-900 dark:text-gray-100 hover:border-blue-400`}
      >
        <span className="truncate">{buttonLabel}</span>
        <div className="flex items-center gap-1 shrink-0">
          {values.length > 0 && (
            <span
              role="button"
              onClick={(e) => { e.stopPropagation(); onChange([]); }}
              className="text-gray-400 hover:text-red-500 text-xs leading-none px-0.5"
              title="Ukloni sve"
            >
              ✕
            </span>
          )}
          <span className="text-gray-400">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full min-w-[300px] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg">
          <div className="p-2 border-b border-gray-100 dark:border-gray-700">
            <input
              autoFocus
              type="text"
              placeholder="Pretraži…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-2 py-1.5 text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-gray-900 dark:text-gray-100 focus:outline-none"
            />
          </div>

          {values.length > 0 && (
            <div className="px-3 py-1.5 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <span className="text-xs text-gray-500 dark:text-gray-400">{values.length} odabrano</span>
              <button
                onClick={() => onChange([])}
                className="text-xs text-red-500 hover:text-red-600"
              >
                Ukloni sve
              </button>
            </div>
          )}

          <ul className="max-h-64 overflow-y-auto">
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-gray-400">Nema rezultata</li>
            ) : (
              filtered.map((o) => {
                const selected = values.includes(o.value);
                return (
                  <li key={o.value}>
                    <button
                      onClick={() => toggle(o.value)}
                      className={`w-full text-left px-3 py-2 text-sm flex items-start gap-2 hover:bg-blue-50 dark:hover:bg-blue-900/20
                        ${selected ? "bg-blue-50 dark:bg-blue-900/30" : ""}`}
                    >
                      <span className={`mt-0.5 w-4 h-4 shrink-0 rounded border flex items-center justify-center text-xs
                        ${selected
                          ? "bg-blue-600 border-blue-600 text-white"
                          : "border-gray-300 dark:border-gray-500"}`}
                      >
                        {selected && "✓"}
                      </span>
                      <div className="min-w-0">
                        <div className={`truncate ${selected ? "text-blue-700 dark:text-blue-300 font-medium" : "text-gray-800 dark:text-gray-200"}`}>
                          {o.label}
                        </div>
                        {o.sub && <div className="text-xs text-gray-400 truncate">{o.sub}</div>}
                      </div>
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function FinanciranjePage() {
  const [selectedDavatelji, setSelectedDavatelji] = useState<string[]>([]);
  const [selectedOrgs, setSelectedOrgs] = useState<string[]>([]);
  const [selectedRazine, setSelectedRazine] = useState<string[]>([]);
  const [godinaOd, setGodinaOd] = useState("");
  const [godinaDo, setGodinaDo] = useState("");
  const [page, setPage] = useState(0);

  const [data, setData] = useState<ApiResponse | null>(null);
  const [stats, setStats] = useState<Statistike | null>(null);
  const [davatelji, setDavatelji] = useState<DavateljRow[]>([]);
  const [orgs, setOrgs] = useState<OrgRow[]>([]);
  const [loading, setLoading] = useState(false);

  const LIMIT = 50;

  // Load static option lists once
  useEffect(() => {
    fetch(`${API}/api/financiranje/davatelji`)
      .then((r) => r.json())
      .then((d) => Array.isArray(d) && setDavatelji(d))
      .catch(() => {});

    fetch(`${API}/api/financiranje/organizacije`)
      .then((r) => r.json())
      .then((d) => Array.isArray(d) && setOrgs(d))
      .catch(() => {});

    fetch(`${API}/api/financiranje/statistike`)
      .then((r) => r.json())
      .then((d) => d?.ukupno && setStats(d))
      .catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: LIMIT.toString(), offset: (page * LIMIT).toString() });
    selectedDavatelji.forEach((d) => params.append("davatelj", d));
    selectedOrgs.forEach((o) => params.append("organizacija", o));
    selectedRazine.forEach((r) => params.append("razina", r));
    if (godinaOd) params.set("godina_od", godinaOd);
    if (godinaDo) params.set("godina_do", godinaDo);

    try {
      const res = await fetch(`${API}/api/financiranje?${params}`);
      const json = await res.json();
      if (json?.results) setData(json);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [selectedDavatelji, selectedOrgs, selectedRazine, godinaOd, godinaDo, page]);

  useEffect(() => {
    const t = setTimeout(fetchData, 200);
    return () => clearTimeout(t);
  }, [fetchData]);

  useEffect(() => {
    setPage(0);
  }, [selectedDavatelji, selectedOrgs, selectedRazine, godinaOd, godinaDo]);

  const totalPages = data ? Math.ceil(data.total / LIMIT) : 0;
  const hasFilters =
    selectedDavatelji.length > 0 || selectedOrgs.length > 0 ||
    selectedRazine.length > 0 || godinaOd || godinaDo;

  const clearAll = () => {
    setSelectedDavatelji([]);
    setSelectedOrgs([]);
    setSelectedRazine([]);
    setGodinaOd("");
    setGodinaDo("");
  };

  const davateljOptions = davatelji.map((d) => ({
    value: d.davatelj,
    label: d.davatelj,
    sub: `${d.broj.toLocaleString()} potpora · ${fmt(d.ukupno)}`,
  }));

  const orgOptions = orgs.map((o) => ({
    value: o.organizacija,
    label: o.organizacija,
    sub: o.oib ? `OIB: ${o.oib} · ${fmt(o.ukupno)}` : fmt(o.ukupno),
  }));

  const razinaOptions = [
    { value: "drzava", label: "Država" },
    { value: "zupanija", label: "Županija" },
    { value: "grad", label: "Grad" },
    { value: "opcina", label: "Općina" },
  ];

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Header title="Financiranje udruga" subtitle="Odobrene potpore 2004–2016 · Ured za udruge" activePath="/financiranje" />

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-4">

        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
          <strong>Napomena:</strong> Podaci pokrivaju 2004–2016. Iznosi konvertirani iz HRK u EUR po fiksnom tečaju <strong>1 EUR = 7,53450 HRK</strong>.
        </div>

        {stats?.ukupno && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Ukupno potpora" value={(stats.ukupno.broj_potpora ?? 0).toLocaleString()} />
            <StatCard label="Ukupni iznos" value={fmt(stats.ukupno.ukupni_iznos ?? null)} />
            <StatCard label="Davatelja" value={davatelji.length.toString()} />
            <StatCard label="Razdoblje" value="2004 – 2016" />
          </div>
        )}

        {/* Filter bar */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Davatelj</label>
              <MultiSelect
                label="Svi davatelji"
                values={selectedDavatelji}
                onChange={setSelectedDavatelji}
                options={davateljOptions}
              />
            </div>

            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Organizacija</label>
              <MultiSelect
                label="Sve organizacije"
                values={selectedOrgs}
                onChange={setSelectedOrgs}
                options={orgOptions}
              />
            </div>

            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Razina vlasti</label>
              <MultiSelect
                label="Sve razine"
                values={selectedRazine}
                onChange={setSelectedRazine}
                options={razinaOptions}
              />
            </div>

            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Godina</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="Od"
                  value={godinaOd}
                  onChange={(e) => setGodinaOd(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <input
                  type="number"
                  placeholder="Do"
                  value={godinaDo}
                  onChange={(e) => setGodinaDo(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          {hasFilters && (
            <div className="mt-3 flex items-center gap-2 flex-wrap text-sm">
              {selectedDavatelji.map((d) => (
                <ActiveFilter key={d} label={d} onRemove={() => setSelectedDavatelji((prev) => prev.filter((v) => v !== d))} />
              ))}
              {selectedOrgs.map((o) => (
                <ActiveFilter key={o} label={o} onRemove={() => setSelectedOrgs((prev) => prev.filter((v) => v !== o))} />
              ))}
              {selectedRazine.map((r) => (
                <ActiveFilter key={r} label={RAZINA_LABELS[r] ?? r} onRemove={() => setSelectedRazine((prev) => prev.filter((v) => v !== r))} />
              ))}
              {(godinaOd || godinaDo) && (
                <ActiveFilter label={`${godinaOd || "…"}–${godinaDo || "…"}`} onRemove={() => { setGodinaOd(""); setGodinaDo(""); }} />
              )}
              <button onClick={clearAll} className="ml-auto text-gray-400 hover:text-red-500 text-xs">
                Obriši sve
              </button>
            </div>
          )}
        </div>

        {/* Results */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>{data?.total != null ? `${data.total.toLocaleString()} rezultata` : "…"}</span>
          </div>

          {loading ? (
            <div className="p-8 text-center text-sm text-gray-400">Učitavam…</div>
          ) : !data?.results?.length ? (
            <div className="p-8 text-center text-sm text-gray-400">Nema rezultata.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2 text-left">Organizacija</th>
                  <th className="px-4 py-2 text-left">Projekt</th>
                  <th className="px-4 py-2 text-left">Davatelj</th>
                  <th className="px-4 py-2 text-center">Razina</th>
                  <th className="px-4 py-2 text-right">Godina</th>
                  <th className="px-4 py-2 text-right">Iznos (EUR)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {data.results.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="px-4 py-2 max-w-[200px]">
                      <div className="truncate font-medium text-gray-900 dark:text-gray-100" title={p.organizacija}>{p.organizacija}</div>
                      {p.oib && <div className="text-xs text-gray-400 font-mono">{p.oib}</div>}
                    </td>
                    <td className="px-4 py-2 max-w-[200px]">
                      <div className="truncate text-xs text-gray-600 dark:text-gray-400" title={p.projekt ?? ""}>{p.projekt ?? "—"}</div>
                    </td>
                    <td className="px-4 py-2 max-w-[180px]">
                      <div className="truncate text-xs text-gray-600 dark:text-gray-400" title={p.davatelj ?? ""}>{p.davatelj ?? "—"}</div>
                    </td>
                    <td className="px-4 py-2 text-center">
                      <span className={`px-1.5 py-0.5 rounded-full text-xs ${RAZINA_COLORS[p.razina] ?? "bg-gray-100 text-gray-600"}`}>
                        {RAZINA_LABELS[p.razina] ?? p.razina}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">{p.godina ?? "—"}</td>
                    <td className="px-4 py-2 text-right font-medium text-gray-900 dark:text-gray-100">{fmt(p.iznos)}</td>
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
              <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
                className="px-3 py-1 border border-gray-200 dark:border-gray-600 rounded-lg disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700">
                ← Prethodno
              </button>
              <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
                className="px-3 py-1 border border-gray-200 dark:border-gray-600 rounded-lg disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700">
                Sljedeće →
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
      <p className="text-xl font-bold text-gray-900 dark:text-gray-100 mt-1">{value}</p>
    </div>
  );
}

function ActiveFilter({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs max-w-[200px]">
      <span className="truncate">{label}</span>
      <button onClick={onRemove} className="hover:text-red-500 ml-0.5 shrink-0">✕</button>
    </span>
  );
}
