import Link from "next/link";
import Header from "./components/Header";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type DatasetRow = {
  ckan_id: string;
  title: string;
  organization: string | null;
  row_count: number | null;
  last_synced_at: string | null;
  status: string;
};

type ZupanijaRow = {
  zupanija: string;
  count: number;
};

async function getDatasets(): Promise<DatasetRow[]> {
  try {
    const res = await fetch(`${API}/api/datasets?status=active`, { cache: "no-store" });
    return res.json();
  } catch {
    return [];
  }
}

async function getZupanije(): Promise<ZupanijaRow[]> {
  try {
    const res = await fetch(`${API}/api/udruge/zupanije`, { cache: "no-store" });
    return res.json();
  } catch {
    return [];
  }
}

function freshness(synced: string | null): { label: string; color: string } {
  if (!synced) return { label: "Never synced", color: "text-red-500" };
  const hours = (Date.now() - new Date(synced).getTime()) / 3_600_000;
  if (hours < 25) return { label: "Fresh", color: "text-green-600" };
  if (hours < 72) return { label: "Stale", color: "text-yellow-600" };
  return { label: "Old", color: "text-red-500" };
}

export default async function Home() {
  const [datasets, zupanije] = await Promise.all([getDatasets(), getZupanije()]);
  const udrugeDataset = datasets.find(
    (d) => d.ckan_id.includes("registar-udruga") || d.title?.toLowerCase().includes("udruga")
  );
  const totalUdruge = zupanije.reduce((s, z) => s + z.count, 0);

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Header title="HR Open Data Pipeline" subtitle="data.gov.hr · automated ETL" activePath="/" />

      <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="Ukupno udruga" value={totalUdruge.toLocaleString()} />
          <StatCard label="Datasets praćeno" value={datasets.length.toString()} />
          <StatCard
            label="Zadnji sync"
            value={
              udrugeDataset?.last_synced_at
                ? new Date(udrugeDataset.last_synced_at).toLocaleString("hr-HR")
                : "—"
            }
          />
        </div>

        <section>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">Aktivni dataseti</h2>
          {datasets.length === 0 ? (
            <p className="text-gray-500 text-sm">Nema podataka — pokrenite pipeline.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {datasets.slice(0, 12).map((d) => {
                const f = freshness(d.last_synced_at);
                return (
                  <div key={d.ckan_id} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{d.title || d.ckan_id}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{d.organization ?? "—"}</p>
                      </div>
                      <span className={`text-xs font-semibold shrink-0 ${f.color}`}>{f.label}</span>
                    </div>
                    <div className="mt-2 flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                      <span>{d.row_count != null ? `${d.row_count.toLocaleString()} rows` : "—"}</span>
                      <span>{d.last_synced_at ? new Date(d.last_synced_at).toLocaleDateString("hr-HR") : "never"}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">Udruge po županijama</h2>
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2 text-left">Županija</th>
                  <th className="px-4 py-2 text-right">Broj udruga</th>
                  <th className="px-4 py-2 text-right">Udio</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {zupanije.map((z) => (
                  <tr key={z.zupanija} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="px-4 py-2 text-gray-800 dark:text-gray-200">
                      <Link
                        href={`/explore/udruge?zupanija=${encodeURIComponent(z.zupanija)}`}
                        className="hover:text-blue-600 dark:hover:text-blue-400"
                      >
                        {z.zupanija}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700 dark:text-gray-300">{z.count.toLocaleString()}</td>
                    <td className="px-4 py-2 text-right text-gray-400 dark:text-gray-500">
                      {totalUdruge > 0 ? `${((z.count / totalUdruge) * 100).toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{value}</p>
    </div>
  );
}
