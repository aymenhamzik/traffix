"""
Notification agent (network). Turns events into messages for the 7 persona pages.

Sources: publications (incidents, floods, rain, late buses, stale data, Route B)
and new decision-log entries (emergency grants and denials, walk signals,
clearance holds, bus priority). Learned (models/notification.joblib): a
classifier deciding which personas an event is relevant to. Its labels come
from rules we wrote (no real users click on alerts), so it learns our
assumptions back: useful for the pipeline, not evidence of user preference.
"""
from ..base import Agent

PERSONAS = ["pedestrian", "car_driver", "bus_passenger", "bus_driver",
            "emergency_crew", "operator", "analyst"]

# event type -> (personas it is relevant to, severity, text template)
RULES = {
    "INCIDENT": ({"car_driver", "operator", "emergency_crew", "bus_driver"}, "warning",
                 "Lane blocked on {edge} (confidence {confidence:.0%}). Cause not determined."),
    "FLOOD": ({"car_driver", "pedestrian", "bus_driver", "bus_passenger", "operator"}, "danger",
              "Flood alert: {edge} is impassable."),
    "RAIN": ({"car_driver", "pedestrian", "bus_driver", "operator"}, "info",
             "Rain: expect traffic about {slow:.0%} slower. Signal timings lengthened."),
    "ROUTE_B": ({"car_driver"}, "info", "Route B around {edge} saves about {saving_s} s."),
    "TRANSIT_LATE": ({"bus_driver", "bus_passenger", "operator"}, "warning",
                     "{vehicle} on line {line} is late (gap {gap:.0f} s)."),
    "DATA_STALE": ({"operator"}, "warning", "Detector {lane} stopped updating; junction on local control."),
    "EMERGENCY_GRANTED": ({"emergency_crew", "operator"}, "info", "Green given to {vehicle} at {tls}."),
    "EMERGENCY_DENIED": ({"emergency_crew", "operator", "analyst"}, "danger",
                         "Priority denied to {vehicle} at {tls}: exit lane full."),
    "EMERGENCY_PREPARE": ({"emergency_crew"}, "info", "{tls} is preparing for {vehicle} (arrival in {eta_s:.0f} s)."),
    "WALK_GRANTED": ({"pedestrian"}, "info", "Walk signal given at {tls} after a long wait."),
    "CLEARANCE": ({"pedestrian", "analyst"}, "info", "Green held at {tls} until the crossing was clear."),
    "TRANSIT_GRANTED": ({"bus_driver", "bus_passenger"}, "info", "Priority given to late bus {vehicle} at {tls}."),
}
EVENT_TYPES = list(RULES)
LOG_EVENTS = {"EMERGENCY_GRANTED_SWITCH": "EMERGENCY_GRANTED", "EMERGENCY_GRANTED_HOLD": "EMERGENCY_GRANTED",
              "EMERGENCY_DENIED_EXIT_FULL": "EMERGENCY_DENIED", "EMERGENCY_PREPARE": "EMERGENCY_PREPARE",
              "PED_SERVICE_GRANTED": "WALK_GRANTED", "CLEARANCE_EXTENDED": "CLEARANCE",
              "TRANSIT_GRANTED_SWITCH": "TRANSIT_GRANTED", "TRANSIT_GRANTED_EXTEND": "TRANSIT_GRANTED"}


def relevance_features(event_type, persona):
    x = [0] * (len(EVENT_TYPES) + len(PERSONAS))
    x[EVENT_TYPES.index(event_type)] = 1
    x[len(EVENT_TYPES) + PERSONAS.index(persona)] = 1
    return x


class NotificationAgent(Agent):
    name = "notification"
    model_file = "notification.joblib"
    KEEP = 400

    def __init__(self, ctx):
        super().__init__(ctx)
        self.seen, self.log_pos = set(), 0

    def relevant(self, event_type, persona):
        if self.model is not None:
            return bool(self.model.predict([relevance_features(event_type, persona)])[0])
        return persona in RULES[event_type][0]

    def emit(self, now, event_type, key, ref=None, **fields):
        if key in self.seen:
            return
        self.seen.add(key)
        _, severity, template = RULES[event_type]
        try:
            text = template.format(**fields)
        except (KeyError, ValueError):
            text = event_type
        for persona in PERSONAS:
            if self.relevant(event_type, persona):
                self.bus.notifications.append({"t": now, "time": self.ctx.clock(now).strftime("%H:%M:%S"),
                                               "persona": persona, "type": event_type,
                                               "severity": severity, "text": text, "ref": ref})
        del self.bus.notifications[:-self.KEEP]

    def step(self, now):
        for p in self.bus.published("INCIDENT"):
            self.emit(now, "INCIDENT", ("INC", p.subject, p.t), edge=p.subject, **p.details)
        for p in self.bus.published("FLOOD"):
            self.emit(now, "FLOOD", ("FLOOD", p.subject), edge=p.subject)
        for p in self.bus.published("WEATHER"):
            if p.details["intensity"] > 0:
                self.emit(now, "RAIN", ("RAIN", p.details["intensity"]),
                          slow=1 - p.details["expected_speed_factor"])
        for p in self.bus.published("ROUTE_B"):
            self.emit(now, "ROUTE_B", ("RB", p.subject, p.t), edge=p.subject, **p.details)
        for p in self.bus.published("TRANSIT_LATE"):
            self.emit(now, "TRANSIT_LATE", ("LATE", p.subject), vehicle=p.subject, **p.details)
        for p in self.bus.published("DATA_STALE"):
            self.emit(now, "DATA_STALE", ("STALE", p.subject, p.t), lane=p.subject)
        entries = self.log.entries[self.log_pos:]
        self.log_pos = len(self.log.entries)
        for e in entries:
            ev = LOG_EVENTS.get(e["reason"])
            if ev:
                d = dict(e["details"])
                d.setdefault("eta_s", 0)
                key = (ev, d.get("vehicle"), e.get("tls")) if d.get("vehicle") else ("LOG", e["id"])
                self.emit(now, ev, key, ref=e["id"], tls=e.get("tls"), **d)
