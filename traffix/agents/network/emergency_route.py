"""
Emergency route coordinator (network). Warns junctions AHEAD of an ambulance.

The junction emergency agents only see an ambulance once it is close. This
agent looks at the whole route and sends an EMERGENCY_PREPARE directive to each
junction the ambulance will reach within prepare_horizon seconds, so masters can
start switching (safely) before it arrives.
Learned: uses the ambulance arrival-time model (models/ambulance_eta.joblib).
"""
from ..base import Agent


class EmergencyRouteAgent(Agent):
    name = "emergency_route"
    model_file = "ambulance_eta.joblib"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.warned = set()

    def eta(self, distance, speed, halting):
        # the model only saw approaches within the detection radius: don't extrapolate
        if self.model is not None and distance <= self.cfg["emergency"]["detect_distance"]:
            return float(self.model.predict([[distance, speed, halting]])[0])
        return distance / max(speed, 8.0)

    def step(self, now):
        horizon = self.cfg["emergency"]["prepare_horizon"]
        for tls, vehicles in self.sensors.approaching.items():
            for v in vehicles:
                if v.kind != "emergency":
                    continue
                stops = [(tls, v.link_index, v.distance)] + list(v.upcoming)
                for j, link, dist in stops:
                    eta = self.eta(dist, v.speed, v.lane_halting)
                    if eta > horizon:
                        break
                    self.send("EMERGENCY_PREPARE", j, now, ttl=6, subject=v.id, link_index=link,
                              eta=round(eta, 1))
                    if (v.id, j) not in self.warned:
                        self.warned.add((v.id, j))
                        self.log.log(now, self.label, "directive", "EMERGENCY_PREPARE", tls=j,
                                     vehicle=v.id, eta_s=eta, distance_m=dist)
