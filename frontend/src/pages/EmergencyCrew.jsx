import NetworkMap from "../components/NetworkMap.jsx";
import { Notifications, Waiting } from "../components/Feed.jsx";

export default function EmergencyCrew({ live }) {
  const amb = (live.vehicles || []).filter((v) => v.kind === "ambulance");
  const decisions = (live.emergency_decisions || []).slice().reverse();
  return (
    <>
      <div><h1>Clear the way</h1>
        <p className="muted">Touhami · ambulances on the move, junctions preparing ahead, grants and denials.</p></div>
      <Waiting live={live} />
      <div className="split">
        <div className="card">
          <h2>{amb.length ? `${amb.length} ambulance${amb.length > 1 ? "s" : ""} active` : "No ambulance active"}</h2>
          <NetworkMap live={live} focus={amb.map((a) => a.id)} highlight={{ incidents: live.incidents?.map((i) => i.subject) }} height={360} />
          <table>
            <thead><tr><th>Time</th><th>Junction</th><th>Vehicle</th><th>Decision</th><th>Via</th></tr></thead>
            <tbody>
              {decisions.slice(0, 12).map((d) => (
                <tr key={d.id}>
                  <td className="mono">{Math.round(d.t)}s</td><td>{d.tls}</td><td className="mono">{d.details.vehicle}</td>
                  <td>{d.reason.includes("DENIED") ? <span className="pill bad">{d.reason.replaceAll("_", " ").toLowerCase()}</span>
                     : d.reason.includes("GRANTED") ? <span className="pill ok">{d.reason.replaceAll("_", " ").toLowerCase()}</span>
                     : d.reason.replaceAll("_", " ").toLowerCase()}</td>
                  <td className="muted">{d.details.via || d.agent}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Notifications live={live} persona="emergency_crew" />
      </div>
    </>
  );
}
