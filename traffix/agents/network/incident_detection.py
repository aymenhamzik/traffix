"""
Incident detection agent (network). PUBLISHES lane-blockage patterns.

Rule: a vehicle stopped mid-block, away from the stop-line queue, for INCIDENT
persist seconds. Learned (models/incident.joblib): a classifier trained on
labelled incidents, normal traffic and rain, so rain slowdowns are not alarms.
Publishes class, confidence and data freshness. Never names a cause.
"""
from ...core.messages import Message
from ..base import Agent

PERSIST_MODEL = 20   # consecutive seconds the model must agree


def edge_of(lane):
    return lane.rsplit("_", 1)[0]


def lane_features(sensors, lane):
    r = sensors.lane(lane)
    sib = [sensors.lane(l) for l in sensors.lanes if edge_of(l) == edge_of(lane) and l != lane]
    sib_speed = max((s.speed for s in sib), default=r.speed)
    return [r.isolated_stops, r.halting, r.vehicles, r.speed, sib_speed, r.occupancy,
            sensors.weather.get("rain", 0.0)]


class IncidentDetectionAgent(Agent):
    name = "incident_detection"
    model_file = "incident.joblib"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.counter, self.reported, self.quiet = {}, {}, {}

    def step(self, now):
        stale_after = self.cfg["safety"]["stale_after"]
        persist = self.cfg["incident"]["persist"]
        probs = {}
        if self.model is not None:                      # one batched prediction per second
            lanes = [l for l, r in self.sensors.readings.items() if r.halting and r.age(now) <= stale_after]
            if lanes:
                p = self.model.predict_proba([lane_features(self.sensors, l) for l in lanes])[:, 1]
                probs = dict(zip(lanes, p))
        for lane, r in self.sensors.readings.items():
            if r.age(now) > stale_after:
                continue
            if self.model is not None:
                prob = float(probs.get(lane, 0.0))
                hit, need = prob > 0.5, PERSIST_MODEL
            else:
                prob, hit, need = None, r.isolated_stops >= 1, persist
            c = self.counter.get(lane, 0)
            c = self.counter[lane] = c + 1 if hit else max(0, c - 1)
            conf = prob if prob is not None else min(0.95, 0.5 + c / (4 * persist))
            edge = edge_of(lane)
            if c >= need and lane not in self.reported:
                self.reported[lane] = now
                self.bus.publish(Message(self.label, "INCIDENT", "all", now, now + 1e9, edge,
                                         details={"lane": lane, "class": "LANE_BLOCKAGE",
                                                  "confidence": round(conf, 2),
                                                  "freshness_s": r.age(now)}))
                self.log.log(now, self.label, "publish", "INCIDENT_SUSPECTED", edge=edge, lane=lane,
                             incident_class="LANE_BLOCKAGE", confidence=conf,
                             data_freshness_s=r.age(now), cause="not determined",
                             method="model" if prob is not None else "rule")
            elif lane in self.reported:
                if c == 0:
                    self.quiet.setdefault(lane, now)
                    if now - self.quiet[lane] >= 60:
                        self.log.log(now, self.label, "publish", "INCIDENT_CLEARED", edge=edge,
                                     lane=lane, reported_at=self.reported.pop(lane))
                        self.bus.unpublish("INCIDENT", edge)
                        self.quiet.pop(lane)
                else:
                    self.quiet.pop(lane, None)
