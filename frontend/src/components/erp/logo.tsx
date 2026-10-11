/**
 * Simple ERP logo: a rounded square in the brand gradient with a white "S" and a green accent dot.
 * The same artwork lives in public/logo.svg (favicon, docs) and in the backend's document_templates.py
 * (invoice / PO headers) - keep the three in step.
 */
import { useId } from "react";

export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  const gradient = `simple-logo-${useId().replace(/:/g, "")}`;
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" className={className} role="img" aria-label="Simple ERP logo">
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0e7490" />
          <stop offset="1" stopColor="#1d4ed8" />
        </linearGradient>
      </defs>
      <rect width="100" height="100" rx="24" fill={`url(#${gradient})`} />
      <path
        d="M69 34C67 26 60 22 50 22C39 22 31 28 31 36C31 44 38 47 50 50C62 53 69 56 69 64C69 72 61 78 50 78C39 78 32 73 30 66"
        fill="none"
        stroke="#fff"
        strokeWidth="9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="79" cy="21" r="5.5" fill="#10b981" />
    </svg>
  );
}

export function Logo({
  showText = true,
  markClass = "h-8 w-8",
  textClass = "font-display tracking-tight text-[var(--foreground)] font-semibold text-sm",
  subClass = "font-normal text-[var(--muted-foreground)]",
}: {
  showText?: boolean;
  markClass?: string;
  textClass?: string;
  subClass?: string;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark className={markClass} />
      {showText && (
        <p className={textClass}>
          Simple <span className={subClass}>ERP</span>
        </p>
      )}
    </div>
  );
}
