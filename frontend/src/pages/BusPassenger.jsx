import { useState } from "react";
import { Notifications, Waiting } from "../components/Feed.jsx";

const LINES = ["L1_east", "L1_west", "L2_south", "L2_north"];

export default function BusPassenger({ live }) {
  const [line, setLine] = useState("L1_east");
  const buses = Object.entries(live.buses || {}).filter(([, b]) => b.line === line);
  return (
    <>
      <div><h1>When is my bus coming?</h1>
        <p className="muted">Mamadou · live buses, gaps between them, and late-running warnings.</p></div>
      <Waiting live={live} />
      <div className="bar">
        {LINES.map((l) => <button key={l} className={l === line ? "primary" : ""} onClick={() => setLine(l)}>{l.replace("_", " ")}</button>)}
      </div>
      <div className="split">
        <div className="card">
          <h2>Buses on line {line.replace("_", " ")}</h2>
          {buses.length === 0 && <span className="muted">No bus of this line tracked yet.</span>}
          <table>
            {buses.length > 0 && <thead><tr><th>Bus</th><th>Next junction</th><th>Distance</th><th>Gap to previous</th><th>Status</th></tr></thead>}
            <tbody>
              {buses.map(([id, b]) => (
                <tr key={id}>
                  <td className="mono">{id.replace("bus_", "")}</td><td>{b.next_junction}</td><td>{b.distance_m} m</td>
                  <td>{Math.round(b.gap_s / 60)} min</td>
                  <td>{b.late ? <span className="pill warn">late</span> : <span className="pill ok">regular</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <span className="muted">Scheduled gap: 4 minutes. A gap above 6 minutes counts as late.</span>
        </div>
        <Notifications live={live} persona="bus_passenger" />
      </div>
    </>
  );
}
