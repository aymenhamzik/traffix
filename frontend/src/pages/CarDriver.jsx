import NetworkMap from "../components/NetworkMap.jsx";
import { Notifications, Stat, Waiting } from "../components/Feed.jsx";

export default function CarDriver({ live }) {
  const routeB = (live.route_b || []).flatMap((r) => r.route_b || []);
  const f = live.forecast || {};
  const busiest = [...(live.junctions || [])].sort((a, b) => b.queue - a.queue)[0];
  return (
    <>
      <div><h1>Your drive through the centre</h1>
        <p className="muted">Faycel · congestion, incidents, floods and Route B suggestions.</p></div>
      <Waiting live={live} />
      <div className="grid g4">
        <Stat label="incidents reported" value={live.incidents?.length || 0} tone={live.incidents?.length ? "#e5604d" : undefined} />
        <Stat label="flooded roads" value={live.floods?.length || 0} tone={live.floods?.length ? "#5c9bea" : undefined} />
        <Stat label="busiest junction" value={busiest ? `${busiest.id} · ${busiest.queue}` : "—"} />
        <Stat label="next 30 min" value={f.level ? `${Math.round(f.level * 100)}%` : "—"} />
      </div>
      <div className="split">
        <div className="card">
          <h2>Map</h2>
          <NetworkMap live={live} highlight={{ incidents: live.incidents?.map((i) => i.subject),
                       floods: live.floods?.map((x) => x.subject), routeB: routeB }} />
          <span className="muted">Red road: blocked lane · dashed blue: flooded · teal: Route B · junction colour: queue and control mode</span>
          {live.route_b?.map((r) => (
            <div key={r.subject} className="note info">Route B around {r.subject}: about {r.saving_s}s faster. Advisory only.</div>
          ))}
        </div>
        <Notifications live={live} persona="car_driver" />
      </div>
    </>
  );
}
