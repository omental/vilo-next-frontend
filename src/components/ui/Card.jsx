export function Card({ title, subtitle, actions, children, className = "" }) {
  return (
    <article className={`card ${className}`.trim()}>
      {(title || subtitle || actions) && (
        <div className="card-header">
          <div>
            {title ? <h3>{title}</h3> : null}
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          {actions ? <div className="card-actions">{actions}</div> : null}
        </div>
      )}
      <div className="card-body">{children}</div>
    </article>
  );
}
