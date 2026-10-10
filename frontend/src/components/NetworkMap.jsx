import { useOnce } from "../api.js";

// Draws the Tunis network, junction states and live vehicles.
// highlight: { incidents: [edge], floods: [edge], routeB: [edge] }, focus: vehicle ids to emphasise
export default function NetworkMap({ live, highlight = {}, focus = [], showCars = true, height = 420 }) {
  const geo = useOnce(live.scenario ? "/network" : null, [live.scenario]);
  if (!geo || live.status === "idle" || live.status === "offline")
    return <div className="map empty" style={{ height }}>Start a scenario to see the map</div>;
  const [x0, y0, x1, y1] = geo.bounds;
  const pad = 60, w = x1 - x0 + 2 * pad, h = y1 - y0 + 2 * pad;
  const X = (x) => x - x0 + pad, Y = (y) => y1 - y + pad;
  const status = Object.fromEntries((live.junctions || []).map((j) => [j.id, j]));
  const inc = new Set(highlight.incidents || []), fl = new Set(highlight.floods || []);
  const rb = new Set(highlight.routeB || []);
  const color = (j) => !j ? "#5a6470" : j.preempt ? "#e5604d" : j.mode === "fixed" ? "#e6a23c"
    : j.mode === "actuated" ? "#c9b25a" : j.queue > 12 ? "#e6a23c" : "#2bc4b5";
  return (
    <svg className="map" viewBox={`0 0 ${w} ${h}`} style={{ height }} role="img"
         aria-label="Map of the central Tunis network with junctions and vehicles">
      {geo.edges.map((e) => {
        const pts = e.shape.map(([x, y]) => `${X(x)},${Y(y)}`).join(" ");
        const stroke = fl.has(e.id) ? "#5c9bea" : inc.has(e.id) ? "#e5604d" : rb.has(e.id) ? "#2bc4b5" : "#323b4a";
        return <polyline key={e.id} points={pts} fill="none" stroke={stroke} strokeLinecap="round"
                         strokeWidth={8 + e.lanes * 5} strokeDasharray={fl.has(e.id) ? "14 8" : undefined}
                         opacity={rb.has(e.id) || inc.has(e.id) || fl.has(e.id) ? 1 : 0.9} />;
      })}
      {showCars && (live.vehicles || []).map((v) => {
        const r = v.kind === "car" ? 6 : 12, f = focus.includes(v.id);
        const fill = v.kind === "ambulance" ? "#ff5a4a" : v.kind === "bus" ? "#5c9bea" : "#b9c4cc";
        return <circle key={v.id} cx={X(v.x)} cy={Y(v.y)} r={f ? 18 : r} fill={fill}
                       stroke={f ? "#fff" : "none"} strokeWidth={f ? 3 : 0} />;
      })}
      {geo.nodes.filter((n) => n.signal).map((n) => (
        <g key={n.id}>
          <circle cx={X(n.x)} cy={Y(n.y)} r={30} fill={color(status[n.id])} />
          <text x={X(n.x)} y={Y(n.y) + 8} textAnchor="middle" fontSize="24" fontFamily="IBM Plex Mono"
                fill="#12161e" fontWeight="600">{n.id}</text>
        </g>
      ))}
    </svg>
  );
}
