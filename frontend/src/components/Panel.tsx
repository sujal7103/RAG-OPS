import type { PropsWithChildren, ReactNode } from "react";

interface PanelProps extends PropsWithChildren {
  title?: string;
  eyebrow?: string;
  actions?: ReactNode;
  className?: string;
}

export function Panel({ title, eyebrow, actions, className, children }: PanelProps) {
  return (
    <section className={`panel ${className || ""}`.trim()}>
      {(title || eyebrow || actions) && (
        <header className="panel-header">
          <div>
            {eyebrow ? <div className="panel-eyebrow">{eyebrow}</div> : null}
            {title ? <h2>{title}</h2> : null}
          </div>
          {actions ? <div className="panel-actions">{actions}</div> : null}
        </header>
      )}
      {children}
    </section>
  );
}
