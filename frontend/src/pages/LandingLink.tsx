/**
 * Minimal in-app navigation stub.
 *
 * A real router (route table per docs/WORKFLOWS.md) arrives with the
 * authenticated app shell; auth-gated routing depends on ADR-P01.
 */
import { useCallback as useCallbackShim } from "react";

export type LinkVariant = "default" | "primary";
export type LinkSize = "md" | "lg";

/** Placeholder link: swaps the visible page via a URL hash. */
export function Link({
  to,
  children,
  variant = "default",
  size = "md",
}: {
  to: string;
  children: React.ReactNode;
  variant?: LinkVariant;
  size?: LinkSize;
}) {
  const base =
    "inline-flex items-center justify-center rounded-md font-medium transition-colors";
  const sizes = { md: "px-4 py-2 text-sm", lg: "px-6 py-3 text-base" };
  const variants = {
    default: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-100",
    primary: "bg-emerald-600 text-white hover:bg-emerald-700",
  };
  return (
    <a href={`#${to}`} className={`${base} ${sizes[size]} ${variants[variant]}`}>
      {children}
    </a>
  );
}

/** Current hash page id ("login", "register", "home"). */
export function useHashPage(): [string, (page: string) => void] {
  const page = window.location.hash.replace("#", "") || "landing";
  const navigate = useCallbackShim((p: string) => {
    window.location.hash = p;
  }, []);
  return [page, navigate];
}
