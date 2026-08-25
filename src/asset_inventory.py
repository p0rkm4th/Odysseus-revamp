from __future__ import annotations
import argparse, concurrent.futures, datetime as dt, errno, fcntl, ipaddress, json, os
from pathlib import Path
import shutil, socket, sqlite3, struct, subprocess, uuid

DB_PATH = Path(os.environ.get("ODY_ASSET_DB", "/app/data/assets/assets.db"))
COMMON_PORTS = (22, 53, 80, 443, 445, 3389, 8000, 8080, 8443)

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def jd(v): return json.dumps(v, sort_keys=True, separators=(",", ":"))

def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=ON")
    c.executescript(
        "CREATE TABLE IF NOT EXISTS assets("
        "id TEXT PRIMARY KEY,name TEXT NOT NULL,type TEXT NOT NULL DEFAULT 'unknown',"
        "status TEXT NOT NULL DEFAULT 'active',manufacturer TEXT,model TEXT,hostname TEXT,"
        "location TEXT,notes TEXT,source TEXT,confidence REAL NOT NULL DEFAULT 1.0,"
        "attributes_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,retired_at TEXT,owner TEXT);"
        "CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name);"
        "CREATE TABLE IF NOT EXISTS identifiers("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,"
        "kind TEXT NOT NULL,value TEXT NOT NULL,confidence REAL NOT NULL DEFAULT 1.0,source TEXT,"
        "first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,UNIQUE(kind,value));"
        "CREATE TABLE IF NOT EXISTS observations("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,asset_id TEXT REFERENCES assets(id) ON DELETE SET NULL,"
        "observed_at TEXT NOT NULL,source TEXT NOT NULL,kind TEXT NOT NULL,confidence REAL NOT NULL DEFAULT 0.5,owner TEXT,"
        "data_json TEXT NOT NULL);"
        "CREATE TABLE IF NOT EXISTS relationships("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,parent_asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,"
        "child_asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,relation TEXT NOT NULL,"
        "started_at TEXT NOT NULL,ended_at TEXT,source TEXT,notes TEXT);"
        "CREATE TABLE IF NOT EXISTS merge_log("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,source_asset_id TEXT NOT NULL,target_asset_id TEXT NOT NULL,"
        "merged_at TEXT NOT NULL,reason TEXT);"
    )
    # The original CMDB predates multi-owner storage.  Additive migration keeps
    # legacy rows intact but leaves them ownerless; owner-aware projections must
    # fail closed or exclude them rather than silently reclassifying them.
    for table, column in (("assets", "owner"), ("observations", "owner")):
        columns = {row[1] for row in c.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
    c.execute("CREATE INDEX IF NOT EXISTS idx_assets_owner ON assets(owner)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_observations_owner ON observations(owner)")
    c.commit()
    return c

def resolve(c, key):
    r = c.execute("SELECT * FROM assets WHERE id=?", (key,)).fetchone()
    if r: return r
    r = c.execute("SELECT a.* FROM identifiers i JOIN assets a ON a.id=i.asset_id WHERE i.value=? LIMIT 1",(key,)).fetchone()
    if r: return r
    rs = c.execute("SELECT * FROM assets WHERE lower(name)=lower(?)",(key,)).fetchall()
    return rs[0] if len(rs)==1 else None

def putid(c, aid, kind, value, confidence=1.0, source="manual"):
    if value is None: return
    value = str(value).strip()
    if not value: return
    if kind=="mac": value=value.lower()
    t=now()
    e=c.execute("SELECT asset_id FROM identifiers WHERE kind=? AND value=?",(kind,value)).fetchone()
    if e and e["asset_id"]!=aid: raise ValueError(f"identifier collision {kind}={value}")
    c.execute(
        "INSERT INTO identifiers(asset_id,kind,value,confidence,source,first_seen,last_seen) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(kind,value) DO UPDATE SET asset_id=excluded.asset_id,"
        "confidence=max(identifiers.confidence,excluded.confidence),source=excluded.source,last_seen=excluded.last_seen",
        (aid,kind,value,float(confidence),source,t,t)
    )

def view(c,r):
    if not r: return None
    d=dict(r); d["attributes"]=json.loads(d.pop("attributes_json") or "{}")
    d["identifiers"]={x["kind"]:x["value"] for x in c.execute("SELECT kind,value FROM identifiers WHERE asset_id=?",(d["id"],))}
    return d

def cmd_add(a):
    c=db(); aid=a.id or str(uuid.uuid4()); t=now()
    c.execute("INSERT INTO assets(id,name,type,status,manufacturer,model,hostname,location,notes,source,confidence,attributes_json,created_at,updated_at)"
              " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (aid,a.name,a.type,a.status,a.manufacturer,a.model,a.hostname,a.location,a.notes,a.source,a.confidence,a.attributes or "{}",t,t))
    for k,v in (("serial",a.serial),("system_uuid",a.system_uuid),("mac",a.mac),("hostname",a.hostname)): putid(c,aid,k,v,a.confidence,a.source)
    c.commit(); print(json.dumps(view(c,c.execute("SELECT * FROM assets WHERE id=?",(aid,)).fetchone()),indent=2,sort_keys=True))

def cmd_update(a):
    c=db(); r=resolve(c,a.asset)
    if not r: raise SystemExit("asset not found: "+a.asset)
    f={}
    for n in ("name","type","status","manufacturer","model","hostname","location","notes","source"):
        v=getattr(a,n,None)
        if v is not None: f[n]=v
    if a.confidence is not None: f["confidence"]=a.confidence
    if a.attributes is not None: f["attributes_json"]=a.attributes
    f["updated_at"]=now()
    c.execute("UPDATE assets SET "+",".join(k+"=?" for k in f)+" WHERE id=?",(*f.values(),r["id"]))
    for k,v in (("serial",a.serial),("system_uuid",a.system_uuid),("mac",a.mac),("hostname",a.hostname)):
        if v is not None: putid(c,r["id"],k,v,a.confidence or r["confidence"],a.source or "manual")
    c.commit(); print(json.dumps(view(c,c.execute("SELECT * FROM assets WHERE id=?",(r["id"],)).fetchone()),indent=2,sort_keys=True))

def cmd_get(a):
    c=db(); r=resolve(c,a.asset)
    if not r: raise SystemExit("asset not found: "+a.asset)
    d=view(c,r)
    d["relationships"]=[dict(x) for x in c.execute("SELECT * FROM relationships WHERE (parent_asset_id=? OR child_asset_id=?) AND ended_at IS NULL",(r["id"],r["id"]))]
    d["recent_observations"]=[dict(x) for x in c.execute("SELECT * FROM observations WHERE asset_id=? ORDER BY id DESC LIMIT 20",(r["id"],))]
    print(json.dumps(d,indent=2,sort_keys=True))

def cmd_list(a):
    c=db(); sql="SELECT * FROM assets WHERE 1=1"; p=[]
    if a.type: sql+=" AND type=?"; p.append(a.type)
    if a.status: sql+=" AND status=?"; p.append(a.status)
    if a.query:
        sql+=" AND (lower(name) LIKE lower(?) OR lower(coalesce(hostname,'')) LIKE lower(?) OR lower(coalesce(model,'')) LIKE lower(?))"
        q="%"+a.query+"%"; p += [q,q,q]
    sql+=" ORDER BY updated_at DESC LIMIT ?"; p.append(a.limit)
    print(json.dumps([view(c,r) for r in c.execute(sql,p)],indent=2,sort_keys=True))

def cmd_observe(a):
    c=db(); aid=None
    if a.asset:
        r=resolve(c,a.asset)
        if not r: raise SystemExit("asset not found: "+a.asset)
        aid=r["id"]
    data=json.loads(a.json) if a.json else {"text":a.text}
    c.execute("INSERT INTO observations(asset_id,observed_at,source,kind,confidence,data_json) VALUES(?,?,?,?,?,?)",
              (aid,now(),a.source,a.kind,a.confidence,jd(data)))
    c.commit(); print(jd({"ok":True,"asset_id":aid,"kind":a.kind}))

def cmd_link(a):
    c=db(); p=resolve(c,a.parent); ch=resolve(c,a.child)
    if not p or not ch: raise SystemExit("parent or child not found")
    cur=c.execute("INSERT INTO relationships(parent_asset_id,child_asset_id,relation,started_at,source,notes) VALUES(?,?,?,?,?,?)",
                  (p["id"],ch["id"],a.relation,now(),a.source,a.notes)); c.commit()
    print(jd({"ok":True,"relationship_id":cur.lastrowid}))

def cmd_unlink(a):
    c=db(); t=now()
    if a.relationship_id:
        c.execute("UPDATE relationships SET ended_at=? WHERE id=? AND ended_at IS NULL",(t,a.relationship_id))
    else:
        p=resolve(c,a.parent); ch=resolve(c,a.child)
        if not p or not ch: raise SystemExit("parent or child not found")
        c.execute("UPDATE relationships SET ended_at=? WHERE parent_asset_id=? AND child_asset_id=? AND relation=? AND ended_at IS NULL",
                  (t,p["id"],ch["id"],a.relation))
    c.commit(); print(jd({"ok":True}))

def cmd_retire(a):
    c=db(); r=resolve(c,a.asset)
    if not r: raise SystemExit("asset not found: "+a.asset)
    t=now(); c.execute("UPDATE assets SET status='retired',retired_at=?,updated_at=? WHERE id=?",(t,t,r["id"])); c.commit()
    print(jd({"ok":True,"asset_id":r["id"]}))

def cmd_merge(a):
    c=db(); s=resolve(c,a.source_asset); d=resolve(c,a.target_asset)
    if not s or not d or s["id"]==d["id"]: raise SystemExit("invalid merge")
    for x in c.execute("SELECT kind,value,confidence,source FROM identifiers WHERE asset_id=?",(s["id"],)):
        try: putid(c,d["id"],x["kind"],x["value"],x["confidence"],x["source"] or "merge")
        except ValueError: pass
    c.execute("UPDATE observations SET asset_id=? WHERE asset_id=?",(d["id"],s["id"]))
    c.execute("UPDATE relationships SET parent_asset_id=? WHERE parent_asset_id=?",(d["id"],s["id"]))
    c.execute("UPDATE relationships SET child_asset_id=? WHERE child_asset_id=?",(d["id"],s["id"]))
    c.execute("INSERT INTO merge_log(source_asset_id,target_asset_id,merged_at,reason) VALUES(?,?,?,?)",(s["id"],d["id"],now(),a.reason))
    c.execute("DELETE FROM assets WHERE id=?",(s["id"],)); c.commit(); print(jd({"ok":True,"source":s["id"],"target":d["id"]}))

def text(path):
    try: return Path(path).read_text(errors="replace").strip()
    except Exception: return ""

def run(argv,timeout=10):
    try:
        cp=subprocess.run(argv,text=True,capture_output=True,timeout=timeout,check=False)
        return cp.returncode,cp.stdout.strip(),cp.stderr.strip()
    except Exception as e: return 127,"",str(e)

def interfaces():
    out=[]; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    for p in sorted(Path("/sys/class/net").glob("*")):
        n=p.name
        if n=="lo": continue
        req=struct.pack("256s",n[:15].encode()); ip=mask=None
        try: ip=socket.inet_ntoa(fcntl.ioctl(s.fileno(),0x8915,req)[20:24])
        except OSError: pass
        try: mask=socket.inet_ntoa(fcntl.ioctl(s.fileno(),0x891b,req)[20:24])
        except OSError: pass
        out.append({"name":n,"mac":text(p/"address").lower(),"ipv4":ip,"netmask":mask})
    s.close(); return out

def default_iface():
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            p=line.split()
            if len(p)>=4 and p[1]=="00000000" and int(p[3],16)&2: return p[0]
    except Exception: pass
    return None

def choose_net():
    ins=interfaces(); pref=default_iface(); cand=[]
    for i in ins:
        if not i["ipv4"] or not i["netmask"]: continue
        try:
            ip=ipaddress.ip_address(i["ipv4"]); net=ipaddress.ip_network(f"{i['ipv4']}/{i['netmask']}",strict=False)
        except Exception: continue
        if ip.is_loopback or ip.is_link_local: continue
        cand.append(((10 if i["name"]==pref else 0)+(3 if ip.is_private else 0),i,net))
    if not cand: return None,None,ins
    _,i,net=sorted(cand,key=lambda x:x[0],reverse=True)[0]
    if net.version==4 and net.prefixlen<24: net=ipaddress.ip_network(f"{i['ipv4']}/24",strict=False)
    return i,net,ins

def arp():
    d={}
    try:
        for line in Path("/proc/net/arp").read_text().splitlines()[1:]:
            p=line.split()
            if len(p)>=6: d[p[0]]={"mac":p[3].lower(),"iface":p[5]}
    except Exception: pass
    return d

def probe(ip,timeout=.18):
    responded = False
    opens = []
    for port in COMMON_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            rc = s.connect_ex((ip, port))
            if rc == 0:
                responded = True
                opens.append(port)
            elif rc == errno.ECONNREFUSED:
                responded = True
        except OSError as e:
            if getattr(e, "errno", None) == errno.ECONNREFUSED:
                responded = True
        finally:
            s.close()
    return {"ip": ip, "tcp_responded": responded, "open_ports": opens}

def maybe_install(ok):
    r={"authorized":bool(ok),"attempted":False,"installed":False}
    if not ok: r["reason"]="not_authorized"; return r
    if shutil.which("ip") and shutil.which("nmap"): r.update(reason="already_present",installed=True); return r
    if os.geteuid()!=0: r["reason"]="non_root_stdlib_fallback"; return r
    plans=[("apt-get",["sh","-lc","apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2 nmap"]),
           ("apk",["apk","add","--no-cache","iproute2","nmap"]),("dnf",["dnf","install","-y","iproute","nmap"]),
           ("microdnf",["microdnf","install","-y","iproute","nmap"]),("yum",["yum","install","-y","iproute","nmap"]),
           ("pacman",["pacman","-Sy","--noconfirm","iproute2","nmap"])]
    for b,cmd in plans:
        if shutil.which(b):
            r["attempted"]=True; rc,_,er=run(cmd,120); r.update(package_manager=b,returncode=rc,stderr=er[-500:],installed=rc==0)
            r["reason"]="installed" if rc==0 else "install_failed_stdlib_fallback"; return r
    r["reason"]="no_package_manager_stdlib_fallback"; return r

def record_net(rep, owner=None):
    owner = str(owner or "").strip()
    if not owner:
        raise ValueError("network observation recording requires an authenticated owner")
    c=db(); t=now()
    for h in rep["hosts"]:
        mac=(h.get("mac") or "").lower(); aid=None
        if mac and mac!="00:00:00:00:00:00":
            e=c.execute(
                "SELECT i.asset_id,a.owner FROM identifiers i JOIN assets a ON a.id=i.asset_id "
                "WHERE i.kind='mac' AND i.value=?", (mac,),
            ).fetchone()
            if e and e["owner"] == owner: aid=e["asset_id"]
            else:
                aid=str(uuid.uuid4())
                # A globally unique legacy identifier cannot be safely reused
                # for another owner.  Keep the observation unattached when the
                # MAC belongs to a different owner instead of merging identity.
                if not e:
                    c.execute("INSERT INTO assets(id,name,type,status,source,confidence,attributes_json,created_at,updated_at,owner) VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (aid,"network-device-"+mac.replace(":","")[-6:],"network_device","observed","network_discovery",.65,"{}",t,t,owner))
                    putid(c,aid,"mac",mac,.9,"network_discovery")
                else:
                    aid = None
        c.execute("INSERT INTO observations(asset_id,observed_at,source,kind,confidence,owner,data_json) VALUES(?,?,?,?,?,?,?)",
                  (aid,t,h.get("source") or "network_discovery",h.get("kind") or "network_host",
                   float(h.get("confidence") or (.75 if mac else .45)),owner,jd(h)))
    c.commit()


def bind_legacy_owner(owner):
    """Bind ownerless legacy CMDB rows during an explicit migration.

    This is intentionally not automatic: an authenticated owner or operator
    must choose the destination owner.  The migration only adds ownership
    metadata and preserves every asset/observation row.
    """
    owner = str(owner or "").strip()
    if not owner:
        raise ValueError("legacy CMDB binding requires an explicit owner")
    c = db()
    assets = c.execute("UPDATE assets SET owner=? WHERE owner IS NULL OR owner=''", (owner,)).rowcount
    observations = c.execute(
        "UPDATE observations SET owner=? WHERE owner IS NULL OR owner=''", (owner,)
    ).rowcount
    c.commit()
    return {"owner": owner, "assets_bound": assets, "observations_bound": observations, "preserved": True}

def cmd_net(a):
    inst = maybe_install(a.install_authorized)
    iface, net, ins = choose_net()
    rep = {
        "timestamp": now(),
        "hostname": socket.gethostname(),
        "install": inst,
        "interfaces": ins,
        "selected_interface": iface,
        "scan_target": str(net) if net else None,
        "ports": list(COMMON_PORTS),
        "hosts": [],
        "method": "python_stdlib_tcp_probe_plus_arp_strong_evidence",
    }
    if not net:
        rep["error"] = "no_usable_ipv4_network"
        print(json.dumps(rep, indent=2, sort_keys=True))
        raise SystemExit(20)

    before = arp()
    local_ip = iface["ipv4"] if iface else None
    targets = [str(x) for x in net.hosts() if str(x) != local_ip][:254]

    probes = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(64, max(1, len(targets)))) as pool:
        for x in pool.map(probe, targets):
            probes[x["ip"]] = x

    after = arp()
    ar = dict(before)
    ar.update(after)

    confirmed = {}
    for ip, x in probes.items():
        if x["open_ports"]:
            confirmed[ip] = {
                "ip": ip,
                "alive": True,
                "open_ports": x["open_ports"],
                "evidence": ["open_tcp_port"],
            }

    for ip, meta in ar.items():
        try:
            if ipaddress.ip_address(ip) not in net:
                continue
        except Exception:
            continue
        mac = (meta.get("mac") or "").lower()
        if not mac or mac == "00:00:00:00:00:00":
            continue
        p = probes.get(ip, {})
        item = confirmed.setdefault(
            ip,
            {
                "ip": ip,
                "alive": True,
                "open_ports": p.get("open_ports", []),
                "evidence": [],
            },
        )
        if "arp" not in item["evidence"]:
            item["evidence"].append("arp")
        item["mac"] = mac
        item["iface"] = meta.get("iface")

    rep["weak_tcp_responses"] = sum(
        1 for x in probes.values() if x.get("tcp_responded") and not x.get("open_ports")
    )
    rep["hosts"] = sorted(
        confirmed.values(),
        key=lambda x: tuple(int(p) for p in x["ip"].split(".")),
    )
    if a.record_observations:
        record_net(rep, owner=a.owner)
        rep["observations_recorded"] = True
    print(json.dumps(rep, indent=2, sort_keys=True))

def cmd_collect(a):
    in_container = Path("/.dockerenv").exists() or bool(os.environ.get("container"))
    d = {
        "timestamp": now(),
        "runtime_hostname": socket.gethostname(),
        "in_container": in_container,
        "machine_id": text("/etc/machine-id"),
        "system_uuid": text("/sys/class/dmi/id/product_uuid"),
        "serial": text("/sys/class/dmi/id/product_serial"),
        "manufacturer": text("/sys/class/dmi/id/sys_vendor"),
        "model": text("/sys/class/dmi/id/product_name"),
        "os_release": text("/etc/os-release"),
        "interfaces": interfaces(),
    }
    for name, cmd in (
        ("lscpu", ["lscpu"]),
        ("lsblk", ["lsblk", "-J", "-O"]),
        ("lspci", ["lspci", "-nn"]),
    ):
        if shutil.which(cmd[0]):
            d[name] = run(cmd, 8)[1]

    if a.record:
        c = db()
        t = now()

        host_hit = None
        for k, v in (("system_uuid", d["system_uuid"]), ("serial", d["serial"])):
            if v:
                host_hit = c.execute(
                    "SELECT asset_id FROM identifiers WHERE kind=? AND value=?",
                    (k, v),
                ).fetchone()
                if host_hit:
                    break

        host_id = host_hit["asset_id"] if host_hit else str(uuid.uuid4())
        host_name = " ".join(
            x for x in (d["manufacturer"], d["model"]) if x
        ).strip() or ("physical-host-" + (d["serial"][-6:] if d["serial"] else host_id[:8]))

        if not host_hit:
            c.execute(
                "INSERT INTO assets(id,name,type,status,manufacturer,model,source,confidence,attributes_json,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    host_id, host_name, "computer", "active",
                    d["manufacturer"], d["model"], "local_collector_host",
                    .95, "{}", t, t,
                ),
            )
        else:
            c.execute(
                "UPDATE assets SET name=?,type='computer',manufacturer=?,model=?,source='local_collector_host',updated_at=? WHERE id=?",
                (host_name, d["manufacturer"], d["model"], t, host_id),
            )

        for k, v in (("system_uuid", d["system_uuid"]), ("serial", d["serial"])):
            putid(c, host_id, k, v, .95, "local_collector_host")

        runtime_id = None
        if in_container:
            hn = d["runtime_hostname"]
            existing = c.execute(
                "SELECT asset_id FROM identifiers WHERE kind='hostname' AND value=?",
                (hn,),
            ).fetchone()
            runtime_id = existing["asset_id"] if existing else str(uuid.uuid4())
            if not existing:
                c.execute(
                    "INSERT INTO assets(id,name,type,status,hostname,source,confidence,attributes_json,created_at,updated_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        runtime_id, hn, "container", "active", hn,
                        "local_collector_runtime", .90, "{}", t, t,
                    ),
                )
            else:
                c.execute(
                    "UPDATE assets SET name=?,type='container',hostname=?,source='local_collector_runtime',updated_at=? WHERE id=?",
                    (hn, hn, t, runtime_id),
                )
            putid(c, runtime_id, "hostname", hn, .95, "local_collector_runtime")
            for i in d["interfaces"]:
                putid(c, runtime_id, "mac", i.get("mac"), .90, "local_collector_runtime")

            rel = c.execute(
                "SELECT id FROM relationships WHERE parent_asset_id=? AND child_asset_id=? AND relation='runs_on' AND ended_at IS NULL",
                (host_id, runtime_id),
            ).fetchone()
            if not rel:
                c.execute(
                    "INSERT INTO relationships(parent_asset_id,child_asset_id,relation,started_at,source,notes)"
                    " VALUES(?,?,?,?,?,?)",
                    (
                        host_id, runtime_id, "runs_on", t,
                        "local_collector", "Container runtime observed on physical host",
                    ),
                )

        c.execute(
            "INSERT INTO observations(asset_id,observed_at,source,kind,confidence,data_json) VALUES(?,?,?,?,?,?)",
            (host_id, t, "local_collector", "hardware_snapshot", .95, jd(d)),
        )
        if runtime_id:
            c.execute(
                "INSERT INTO observations(asset_id,observed_at,source,kind,confidence,data_json) VALUES(?,?,?,?,?,?)",
                (runtime_id, t, "local_collector", "runtime_snapshot", .90, jd({
                    "hostname": d["runtime_hostname"],
                    "interfaces": d["interfaces"],
                    "os_release": d["os_release"],
                })),
            )
        c.commit()
        d["host_asset_id"] = host_id
        d["runtime_asset_id"] = runtime_id

    print(json.dumps(d, indent=2, sort_keys=True))

def cmd_summary(a):
    c=db()
    out={"database":str(DB_PATH),"assets":c.execute("SELECT count(*) FROM assets").fetchone()[0],
         "active":c.execute("SELECT count(*) FROM assets WHERE status='active'").fetchone()[0],
         "observed":c.execute("SELECT count(*) FROM assets WHERE status='observed'").fetchone()[0],
         "observations":c.execute("SELECT count(*) FROM observations").fetchone()[0],
         "relationships":c.execute("SELECT count(*) FROM relationships WHERE ended_at IS NULL").fetchone()[0],
         "by_type":{r[0]:r[1] for r in c.execute("SELECT type,count(*) FROM assets GROUP BY type ORDER BY type")}}
    print(json.dumps(out,indent=2,sort_keys=True))

def parser():
    p=argparse.ArgumentParser(prog="python -m src.asset_inventory"); s=p.add_subparsers(dest="cmd",required=True)
    x=s.add_parser("init"); x.set_defaults(func=lambda a:(db().close(),print(jd({"ok":True,"database":str(DB_PATH)}))))
    x=s.add_parser("migrate-owner"); x.add_argument("--owner", required=True); x.set_defaults(func=lambda a: print(jd(bind_legacy_owner(a.owner))))
    x=s.add_parser("summary"); x.set_defaults(func=cmd_summary)
    x=s.add_parser("add"); x.add_argument("--id"); x.add_argument("--name",required=True); x.add_argument("--type",default="unknown")
    x.add_argument("--status",default="active"); x.add_argument("--manufacturer"); x.add_argument("--model"); x.add_argument("--serial")
    x.add_argument("--system-uuid"); x.add_argument("--hostname"); x.add_argument("--mac"); x.add_argument("--location"); x.add_argument("--notes")
    x.add_argument("--source",default="manual"); x.add_argument("--confidence",type=float,default=1.0); x.add_argument("--attributes"); x.set_defaults(func=cmd_add)
    x=s.add_parser("update"); x.add_argument("asset")
    for f in ("name","type","status","manufacturer","model","serial","system_uuid","hostname","mac","location","notes","source"):
        x.add_argument("--"+f.replace("_","-"),dest=f)
    x.add_argument("--confidence",type=float); x.add_argument("--attributes"); x.set_defaults(func=cmd_update)
    x=s.add_parser("get"); x.add_argument("asset"); x.set_defaults(func=cmd_get)
    for n in ("list","search"):
        x=s.add_parser(n); x.add_argument("query",nargs="?"); x.add_argument("--type"); x.add_argument("--status"); x.add_argument("--limit",type=int,default=100); x.set_defaults(func=cmd_list)
    x=s.add_parser("observe"); x.add_argument("--asset"); x.add_argument("--kind",required=True); x.add_argument("--source",default="manual")
    x.add_argument("--confidence",type=float,default=.5); x.add_argument("--json"); x.add_argument("--text"); x.set_defaults(func=cmd_observe)
    x=s.add_parser("link"); x.add_argument("parent"); x.add_argument("child"); x.add_argument("--relation",default="contains"); x.add_argument("--source",default="manual"); x.add_argument("--notes"); x.set_defaults(func=cmd_link)
    x=s.add_parser("unlink"); x.add_argument("--relationship-id",type=int); x.add_argument("--parent"); x.add_argument("--child"); x.add_argument("--relation",default="contains"); x.set_defaults(func=cmd_unlink)
    x=s.add_parser("retire"); x.add_argument("asset"); x.set_defaults(func=cmd_retire)
    x=s.add_parser("merge"); x.add_argument("source_asset"); x.add_argument("target_asset"); x.add_argument("--reason"); x.set_defaults(func=cmd_merge)
    x=s.add_parser("collect-local"); x.add_argument("--record",action="store_true"); x.set_defaults(func=cmd_collect)
    x=s.add_parser("network-discover"); x.add_argument("--owner", required=True); x.add_argument("--install-authorized",action="store_true"); x.add_argument("--record-observations",action="store_true"); x.set_defaults(func=cmd_net)
    return p

def main():
    a=parser().parse_args(); a.func(a); return 0
if __name__=="__main__": raise SystemExit(main())
