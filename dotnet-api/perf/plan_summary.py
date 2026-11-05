"""Summarize the output of perf/measure_sql.sh: logical reads, CPU/elapsed time, and the actual plan operators.

    perf/measure_sql.sh 0 | python3 perf/plan_summary.py
"""
import re
import sys
import xml.etree.ElementTree as ET

text = sys.stdin.read()
NS = {"p": "http://schemas.microsoft.com/sqlserver/2004/07/showplan"}

for section in text.split("=== ")[1:]:
    title, body = section.split(" ===", 1)
    print(f"[{title}]")
    for m in re.finditer(r"Table '(\w+)'\. Scan count (\d+), logical reads (\d+)", body):
        if not m.group(1).startswith("Work"):
            print(f"  logical reads {int(m.group(3)):>10,}  {m.group(1)} (scans {m.group(2)})")
    times = re.findall(r"CPU time = (\d+) ms,\s+elapsed time = (\d+) ms", body)
    if times:
        cpu, elapsed = max(times, key=lambda t: int(t[1]))
        print(f"  CPU {int(cpu):,} ms, elapsed {int(elapsed):,} ms")
    xml_start = body.find("<ShowPlanXML")
    if xml_start >= 0:
        root = ET.fromstring(body[xml_start:body.index("</ShowPlanXML>") + len("</ShowPlanXML>")])
        for op in root.iter(f"{{{NS['p']}}}RelOp"):
            counters = op.find("p:RunTimeInformation", NS)
            actual = sum(int(c.get("ActualRows", 0)) for c in counters) if counters is not None else 0
            obj = op.find("./*/p:Object", NS)   # only the operator's own table/index, not a descendant's
            target = f" {obj.get('Table')}.{obj.get('Index')}" if obj is not None and obj.get("Index") else ""
            name = op.get("PhysicalOp")
            if name in ("Compute Scalar", "Parallelism"):
                continue
            print(f"  {name:<24}{target:<50} actual rows {actual:>10,}")
