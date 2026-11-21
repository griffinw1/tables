#!/usr/bin/env python3
"""Listen for "Pull again" taps from the Tables page and run a fresh check on this Mac.

The page POSTs {"party": N} to https://ntfy.sh/<topic>; this script streams that topic,
runs scripts/publish.sh (party 4 + the tapped size), and reports progress on <topic>-s
as JSON: started / busy / cooldown / done / failed. Runs under launchd
(scripts/com.dallasreswatch.pull.plist, KeepAlive). Log: ~/.tables/pull.log
"""
import datetime as dt, json, os, subprocess, sys, time, urllib.request
from zoneinfo import ZoneInfo
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TOPIC = (HERE / "scripts" / "pull_topic.txt").read_text().strip()
NT = "https://ntfy.sh/"
COOLDOWN_MIN = 8
ALL = "resy,sevenrooms,opentable,tock,phone,walkin,unknown"


def log(*a):
    print(dt.datetime.now().strftime("%m-%d %H:%M:%S"), *a, flush=True)


def tell(**m):
    try:
        urllib.request.urlopen(urllib.request.Request(NT + TOPIC + "-s", data=json.dumps(m).encode(), method="POST"), timeout=15)
    except Exception as e:
        log("status send failed:", e)


def last_pull(party=4, city="dallas"):
    f = HERE / "cities" / city / "results" / f"p{party}.json"
    try:
        return dt.datetime.fromisoformat(json.loads(f.read_text())["generated_at"])
    except Exception:
        return None


LOCK = Path.home() / ".tables" / "run.lock"


def check_date(city, party, date):
    """Check one night for one city + party, commit cities/<city>/results/custom/<date>-p<party>.json, push."""
    out = HERE / "cities" / city / "results" / "custom" / f"{date}-p{party}.json"
    if out.exists() and time.time() - out.stat().st_mtime < 30 * 60:
        log("custom fresh", city, date, party); tell(state="done", date=date, city=city, party=party); return
    tell(state="queued" if LOCK.exists() else "started", date=date, city=city, party=party)
    for _ in range(120):  # wait up to 20 min for a running publish to finish
        try:
            LOCK.mkdir(parents=True); break
        except FileExistsError:
            time.sleep(10)
    else:
        tell(state="failed", date=date, city=city, party=party, why="busy"); return
    try:
        tell(state="started", date=date, city=city, party=party)
        out.parent.mkdir(parents=True, exist_ok=True)
        py = str(HERE / ".venv" / "bin" / "python")
        with open(Path.home() / ".tables/launchd.log", "a") as lg:
            lg.write(f"\n=== date check {city} {date} p{party} {dt.datetime.now():%F %T} ===\n"); lg.flush()
            rc = subprocess.run([py, "check.py", "--city", city, "--party", str(party), "--start-date", date, "--end-date", date,
                                 "--out", str(out)], cwd=HERE, stdout=lg, stderr=subprocess.STDOUT).returncode
            if rc == 0:
                git = lambda *a: subprocess.run(["git", *a], cwd=HERE, stdout=lg, stderr=subprocess.STDOUT).returncode
                git("add", str(out.relative_to(HERE)))
                git("commit", "-qm", f"date check: {city} {date} for {party}")
                for i in range(4):
                    git("pull", "-q", "--rebase", "--autostash")
                    if git("push", "-q") == 0:
                        break
                    time.sleep(5 * (i + 1))
        log("date check", city, date, party, "rc", rc)
        tell(state="done" if rc == 0 else "failed", date=date, city=city, party=party)
    finally:
        try:
            LOCK.rmdir()
        except OSError:
            pass


def handle(body):
    try:
        msg = json.loads(body)
        party, city = int(msg.get("party", 4)), str(msg.get("city", "dallas"))
        date = str(msg.get("date") or "")
    except Exception:
        party, city, date = 4, "dallas", ""
    cities = {c["slug"]: c for c in json.loads((HERE / "cities.json").read_text())}
    if city not in cities:
        city = "dallas"
    if not 2 <= party <= 8:
        party = 4
    if date:
        try:
            d = dt.date.fromisoformat(date)
        except ValueError:
            return
        today = dt.datetime.now(ZoneInfo(cities[city].get("tz", "America/Chicago"))).date()
        if not today <= d <= today + dt.timedelta(days=90):
            tell(state="failed", date=date, city=city, party=party, why="range"); return
        check_date(city, party, date); return
    if Path.home().joinpath(".tables/run.lock").exists():
        log("busy"); tell(state="busy"); return
    lp = last_pull(party, city)
    now = dt.datetime.now(dt.timezone.utc)
    if lp and (now - lp).total_seconds() < COOLDOWN_MIN * 60:
        nxt = lp + dt.timedelta(minutes=COOLDOWN_MIN)
        log("cooldown"); tell(state="cooldown", mins=int((now - lp).total_seconds() // 60), next=nxt.isoformat()); return
    log(f"pull requested (party {party})"); tell(state="started", party=party)
    env = dict(os.environ, CITIES=city)
    if party == 4:
        env["NO_SIZES"] = "1"
    else:
        env["PULL_SIZES"] = str(party)
    with open(Path.home() / ".tables/launchd.log", "a") as out:
        out.write(f"\n=== manual pull (party {party}) {dt.datetime.now():%F %T} ===\n"); out.flush()
        rc = subprocess.run(["bash", "scripts/publish.sh"], cwd=HERE, env=env, stdout=out, stderr=subprocess.STDOUT).returncode
    if rc == 75:
        tell(state="busy"); return
    if rc == 0:
        lp = last_pull(4, city)
        log("done", rc); tell(state="done", at=(lp or now).isoformat())
    else:
        log("failed", rc); tell(state="failed", rc=rc)


def main():
    since = "10s"
    while True:
        try:
            with urllib.request.urlopen(f"{NT}{TOPIC}/json?since={since}", timeout=120) as r:
                log("listening on", TOPIC)
                for line in r:
                    ev = json.loads(line)
                    if ev.get("event") != "message":
                        continue
                    since = ev["id"]
                    # ignore taps older than 2 min (e.g. replayed after a reconnect)
                    if time.time() - ev.get("time", 0) > 120:
                        continue
                    handle(ev.get("message", ""))
        except Exception as e:
            log("stream ended:", e)
        time.sleep(10)


if __name__ == "__main__":
    sys.exit(main())
