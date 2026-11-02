import {
  AlertCircle,
  CheckCircle2,
  CircleHelp,
  LoaderCircle,
  Radio
} from "lucide-react";

export function Panel({ title, description, eyebrow, icon: Icon, actions, className = "", children }) {
  return <section className={`panel ${className}`.trim()}>
    {(eyebrow || title || description || actions) && <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        {eyebrow && <p className="eyebrow">{Icon && <Icon size={15} />}{eyebrow}</p>}
        {title && <h2 className="panel-title">{title}</h2>}
        {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{description}</p>}
      </div>
      {actions}
    </div>}
    {children}
  </section>;
}

export function MetricCard({ label, value, subtitle, className = "" }) {
  return <div className={`metric-card ${className}`.trim()}>
    <span className="metric-label">{label}</span>
    <strong className="metric-value">{value}</strong>
    {subtitle && <span className="metric-subtitle">{subtitle}</span>}
  </div>;
}

const STATUS_CONFIG = {
  demo: { label: "Demo", className: "status-badge-demo" },
  live: { label: "Live", className: "status-badge-live" },
  complete: { label: "Complete", className: "status-badge-complete" },
  incomplete: { label: "Incomplete", className: "status-badge-incomplete" },
  unavailable: { label: "Unavailable", className: "status-badge-unavailable" },
  error: { label: "Error", className: "status-badge-error" }
};

export function StatusBadge({ status, label }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.unavailable;
  return <span className={`status-badge ${config.className}`}><span className="status-badge-dot" />{label || config.label}</span>;
}

export function PageHeader({ eyebrow, title, description, actions, className = "" }) {
  return <div className={`page-header ${className}`.trim()}>
    <div>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1 className="page-title">{title}</h1>
      {description && <p className="page-description">{description}</p>}
    </div>
    {actions}
  </div>;
}

export function LoadingState({ text = "Loading...", className = "" }) {
  return <div className={`feedback-state feedback-loading ${className}`.trim()} role="status" aria-live="polite">
    <LoaderCircle size={18} className="animate-spin text-cyan" aria-hidden="true" />
    <span>{text}</span>
  </div>;
}

export function EmptyState({ icon: Icon = Radio, text, title, action, className = "" }) {
  return <div className={`feedback-state feedback-empty ${className}`.trim()} role="status">
    <Icon className="feedback-icon" size={28} aria-hidden="true" />
    {title && <strong className="feedback-title">{title}</strong>}
    <p>{text}</p>
    {action}
  </div>;
}

export function ErrorState({ message, title = "Something went wrong", className = "" }) {
  return <div className={`feedback-error ${className}`.trim()} role="alert" aria-live="assertive">
    <AlertCircle size={18} aria-hidden="true" />
    <div><strong>{title}</strong><p>{message}</p></div>
  </div>;
}

export function SuccessState({ message }) {
  return <div className="feedback-success" role="status" aria-live="polite">
    <CheckCircle2 size={18} aria-hidden="true" />
    <span>{message}</span>
  </div>;
}

export { CircleHelp };
