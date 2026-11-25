// A row of small "label: number" cards, used for status and severity counts.
export default function CountCards({ title, counts }: { title: string; counts: Record<string, number> }) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      <div className="cards">
        {Object.entries(counts).map(([label, count]) => (
          <div key={label} className={`card card-${label.toLowerCase()}`}>
            <div className="card-count">{count}</div>
            <div className="card-label">{label}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
