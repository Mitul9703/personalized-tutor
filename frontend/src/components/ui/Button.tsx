import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Variant = "primary" | "ghost" | "soft";

export function Button({
  className,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition disabled:opacity-40 disabled:pointer-events-none";
  const variants: Record<Variant, string> = {
    primary: "bg-brand text-white hover:bg-indigo-600 px-4 py-2",
    ghost: "text-ink/60 hover:bg-black/5 hover:text-ink px-2.5 py-1.5",
    soft: "bg-brandsoft text-brand hover:bg-indigo-100 px-3 py-1.5",
  };
  return <button className={cn(base, variants[variant], className)} {...props} />;
}
