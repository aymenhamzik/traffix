"""
Live mode: runs ONE simulation in a background thread, paced for watching,
and keeps a snapshot of everything the persona pages need.
"""
import json
import os
import threading
import time
from datetime import datetime

import sumo
import sumolib

from ..core import config
from ..core.decision_log import DecisionLog
from ..demand.generator import DemandGenerator
from ..orchestration.system import TraffixSystem
from ..simulation.backend import traci
from ..simulation.network_model import load_models
from ..simulation.world import World

SUMO_HOME = os.environ.get("SUMO_HOME", sumo.SUMO_HOME)


def network_geometry(net_file):
    net = sumolib.net.readNet(net_file)
    nodes = [{"id": n.getID(), "x": n.getCoord()[0], "y": n.getCoord()[1],
              "signal": n.getType() == "traffic_light"} for n in net.getNodes()]
    edges = [{"id": e.getID(), "from": e.getFromNode().getID(), "to": e.getToNode().getID(),
              "name": e.getName(), "lanes": len([l for l in e.getLanes() if l.allows("passenger")]),
              "shape": [list(p) for p in e.getShape()]}
             for e in net.getEdges() if not e.getFunction() and e.allows("passenger")]
    xs = [n["x"] for n in nodes]
    ys = [n["y"] for n in nodes]
    return {"nodes": nodes, "edges": edges, "bounds": [min(xs), min(ys), max(xs), max(ys)]}


class LiveRun:
    def __init__(self, scenario, seed=1, speed=4.0, controller="traffix"):
        self.scenario, self.seed, self.speed, self.controller = scenario, seed, speed, controller
        self.lock = threading.Lock()
        self.snapshot = {"status": "starting"}
        self.log = DecisionLog()
        self.running = False
        net = config.network_files()[0]
        self.geometry = network_geometry(net)
        gen = DemandGenerator(net)
        self.routes, self.meta = gen.build(scenario, config.scenarios()[scenario], seed,
                                           config.path("data", "generated", "live"))

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False

    def _run(self):
        net = config.network_files()[0]
        traci.start([os.path.join(SUMO_HOME, "bin", "sumo"), "-n", net, "-r", self.routes,
                     "--time-to-teleport", "300", "--ignore-route-errors", "true",
                     "--no-step-log", "true", "--no-warnings", "true", "--seed", str(self.seed)])
        models = load_models(net)
        start = datetime.strptime(self.meta["start"], "%Y-%m-%d %H:%M")
        self.system = TraffixSystem(self.controller, models, net, self.log, start)
        self.system.start(0)
        world = World(self.meta["events"], models, self.system.sensors)
        end = self.meta["duration"]
        try:
            while self.running and traci.simulation.getTime() < end:
                t0 = time.time()
                traci.simulationStep()
                now = traci.simulation.getTime()
                world.step(now)
                self.system.step(now)
                snap = self._snapshot(now, models)
                with self.lock:
                    self.snapshot = snap
                time.sleep(max(0.0, 1.0 / self.speed - (time.time() - t0)))
        finally:
            traci.close()
            with self.lock:
                self.snapshot["status"] = "finished"

    def _snapshot(self, now, models):
        s, bus = self.system.sensors, self.system.bus
        vehicles = []
        for v in traci.vehicle.getIDList():
            x, y = traci.vehicle.getPosition(v)
            vc = traci.vehicle.getVehicleClass(v)
            vehicles.append({"id": v, "x": round(x, 1), "y": round(y, 1),
                             "kind": "ambulance" if vc == "emergency" else "bus" if vc == "bus" else "car",
                             "line": traci.vehicle.getLine(v) if vc == "bus" else "",
                             "speed": round(traci.vehicle.getSpeed(v), 1)})
        junctions = []
        for tls, st in bus.status.items():
            m = models[tls]
            junctions.append({
                "id": tls, "name": m.name, "mode": st["mode"], "queue": st["queue_total"],
                "preempt": st["preempt"],
                "crossings": [{"id": c, "walk": m.crossing_green(st["green"], c),
                               "waiting": s.waiting_at.get(c, (0, 0))[0],
                               "longest_wait": round(s.waiting_at.get(c, (0, 0))[1]),
                               "on_crossing": len(s.on_crossing.get(c, []))} for c in m.crossings]})
        pubs = lambda k: [{"subject": p.subject, "t": p.t, **p.details} for p in bus.published(k)]
        return {
            "status": "running", "scenario": self.scenario, "t": now,
            "clock": self.system.ctx.clock(now).strftime("%Y-%m-%d %H:%M:%S"),
            "duration": self.meta["duration"], "junctions": junctions, "vehicles": vehicles,
            "incidents": pubs("INCIDENT"), "floods": pubs("FLOOD"), "route_b": pubs("ROUTE_B"),
            "stale": pubs("DATA_STALE"), "weather": s.weather, "forecast": bus.forecast,
            "buses": self.system.supermaster.transit.state if self.system.supermaster else {},
            "notifications": bus.notifications[-150:],
            "decisions": self.log.entries[-60:],
            "emergency_decisions": [e for e in self.log.entries[-3000:]
                                    if e["reason"].startswith(("EMERGENCY", "RECOVER"))][-40:],
            "transit_decisions": [e for e in self.log.entries[-3000:]
                                  if e["reason"].startswith(("TRANSIT", "BUS_"))][-150:],
            "counts": {"vehicles": len(vehicles), "pedestrians": traci.person.getIDCount(),
                       "decisions": len(self.log.entries)}}

    def state(self):
        with self.lock:
            return dict(self.snapshot)
