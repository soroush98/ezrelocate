import type { ReactNode } from "react";

type Variant = "default" | "brand" | "info" | "warm" | "outline";

const variantClass: Record<Variant, string> = {
  default: "bg-slate-100 text-slate-700",
  brand:   "bg-brand-50 text-brand-700",
  info:    "bg-sky-50 text-sky-700",
  warm:    "bg-amber-50 text-amber-800",
  outline: "border border-slate-200 text-slate-600 bg-white",
};

export function Pill({
  children,
  icon,
  variant = "default",
  className = "",
}: {
  children: ReactNode;
  icon?: ReactNode;
  variant?: Variant;
  className?: string;
}) {
  return (
    <span
      className={
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-5 " +
        variantClass[variant] +
        " " +
        className
      }
    >
      {icon && <span className="-ml-0.5">{icon}</span>}
      {children}
    </span>
  );
}
