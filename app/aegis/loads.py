import logging
import threading
import time
from aegis.k6job import K6Job, arrival_rate_options

logger = logging.getLogger(__name__)
LOAD_LABELS = {"app.kubernetes.io/part-of": "aegis-load"}
START_SECONDS = 15


class LoadBusy(Exception):
    pass


class UnknownProfile(Exception):
    pass


# k6 stages of a profile: every [factor, seconds] goes to factor * C req/s in that time.
def profile_stages(profile, capacity_rps):
    stages = []
    for factor, seconds in profile["stages"]:
        stages.append({"target": round(factor * capacity_rps, 1), "duration": str(int(seconds)) + "s"})
    return stages


def profile_seconds(profile):
    total = 0
    for factor, seconds in profile["stages"]:
        total += seconds
    return total


def profile_peak(profile, capacity_rps):
    peak = profile["start"]
    for factor, seconds in profile["stages"]:
        peak = max(peak, factor)
    return round(peak * capacity_rps, 1)


# Starts and stops the k6 loads of the monitor buttons, one at a time, each with a time limit.
class LoadController:
    def __init__(self, config, job=None):
        settings = config["load"]
        self.profiles = settings["profiles"]
        self.capacity_rps = float(config["capacity_rps"])
        self.max_seconds = settings["max_seconds"]
        self.pre_allocated_vus = settings["pre_allocated_vus"]
        self.max_vus = settings["max_vus"]
        self.job = job
        if job is None:
            self.job = K6Job(settings["job_name"], config["kubernetes"]["namespace"], config["calibration"]["k6_image"],
                             config["calibration"]["target_url"], LOAD_LABELS, self.max_seconds)
        self.current = None
        self.lock = threading.Lock()

    def listing(self):
        found = []
        for name in self.profiles:
            profile = self.profiles[name]
            found.append({"name": name, "seconds": profile_seconds(profile),
                          "peak_rps": profile_peak(profile, self.capacity_rps)})
        return found

    # The running load, or None once its Job ended or its time is over.
    def running(self):
        if self.current is None:
            return None
        if time.time() > self.current["ends_at"] + 60 or self.job.finished():
            self.current = None
        return self.current

    def status(self):
        with self.lock:
            return {"profiles": self.listing(), "running": self.running(), "capacity_rps": self.capacity_rps}

    def start(self, name):
        if name not in self.profiles:
            raise UnknownProfile(name)
        with self.lock:
            if self.running() is not None:
                raise LoadBusy(self.current["profile"])
            profile = self.profiles[name]
            seconds = profile_seconds(profile)
            if seconds > self.max_seconds:
                raise UnknownProfile(name + " is longer than load.max_seconds")
            options = arrival_rate_options(round(profile["start"] * self.capacity_rps, 1),
                                           profile_stages(profile, self.capacity_rps),
                                           self.pre_allocated_vus, self.max_vus)
            self.job.delete(wait_seconds=60)
            self.job.create(options)
            now = time.time()
            self.current = {"profile": name, "started_at": now, "ends_at": now + START_SECONDS + seconds,
                            "seconds": seconds}
            logger.warning("Load %s started from the monitor (%s s)", name, seconds)
            return self.current

    def stop(self):
        with self.lock:
            self.job.delete(wait_seconds=0)
            stopped = self.current
            self.current = None
            if stopped is not None:
                logger.warning("Load %s stopped from the monitor", stopped["profile"])
            return stopped
