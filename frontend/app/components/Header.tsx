import Link from "next/link";
import ThemeToggle from "./ThemeToggle";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/explore/udruge", label: "Udruge" },
  { href: "/financiranje", label: "Financiranje" },
  { href: "/pipeline", label: "Pipeline" },
];

export default function Header({
  title,
  subtitle,
  activePath,
}: {
  title: string;
  subtitle?: string;
  activePath: string;
}) {
  return (
    <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">{title}</h1>
        {subtitle && <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-6">
        <nav className="flex gap-4 text-sm font-medium">
          {NAV.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={
                activePath === href
                  ? "text-blue-600 dark:text-blue-400"
                  : "text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400"
              }
            >
              {label}
            </Link>
          ))}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
