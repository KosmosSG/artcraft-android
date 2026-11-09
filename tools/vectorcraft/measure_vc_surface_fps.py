#!/usr/bin/env python3
"""On-device Vulkan SurfaceFlinger presentation benchmark for Android test APK.

Usage, with USB or wireless ADB paired:
  python3 tools/vectorcraft/measure_vc_surface_fps.py --label android21-menu --seconds 15
  python3 tools/vectorcraft/measure_vc_surface_fps.py --label android22-menu --seconds 15

While the tool samples, repeatedly scroll the same long Vc menu / canvas.
The app's VC_PERF_UI_PROXY diagnostic is not a presentation benchmark.
This tool uses SurfaceFlinger's ACTUAL presentation timestamps when exposed.
If no eligible surface/timestamps exist, it says UNAVAILABLE, never invents FPS.
"""
import argparse
import csv
import json
from pathlib import Path
import statistics
import subprocess
import time
from datetime import datetime, timezone

def adb(*args):
    result=subprocess.run(["adb",*args],capture_output=True,text=True,timeout=45)
    if result.returncode:
        raise RuntimeError("adb command failed: "+" ".join(args)+"\n"+result.stderr[-600:])
    return result.stdout

def pick_layer(raw,package):
    layers=[line.strip() for line in raw.splitlines() if package in line]
    if not layers: raise RuntimeError("NO MATCHING SurfaceFlinger layer. Open app first.")
    def priority(name):
        s=name.lower()
        return (int("surfaceview" in s)*8 + int("blast" in s)*4
                + int("native" in s)*2 - int("splash" in s)*10
                - int("background" in s)*5)
    return max(layers,key=priority)

def collect(package,label,seconds,folder):
    try:
        layer=pick_layer(adb("shell","dumpsys","SurfaceFlinger","--list"),package)
        print("Selected Vulkan surface:",layer)
        adb("shell","dumpsys","SurfaceFlinger","--latency-clear",layer)
        print(f"START. Scroll/pinch the SAME test gesture for {seconds}s now.",flush=True)
        time.sleep(seconds)
        raw=adb("shell","dumpsys","SurfaceFlinger","--latency",layer)
    except Exception as e:
        print("Presentation timing UNAVAILABLE:",e)
        return 2
    folder.mkdir(parents=True,exist_ok=True)
    (folder/(label+"-raw-sf.txt")).write_text(raw)
    timestamps=[]
    for line in raw.splitlines()[1:]:
        cols=line.split()
        if len(cols)!=3: continue
        try: desired,presented,ready=map(int,cols)
        except ValueError: continue
        if 0 < presented < 9_223_372_036_854_775_807:
            timestamps.append(presented)
    timestamps=sorted(set(timestamps))
    intervals=[(b-a)/1e6 for a,b in zip(timestamps,timestamps[1:])
               if 1.0 <= (b-a)/1e6 <= 1000.0]
    if len(intervals)<10:
        print("Presentation timing UNAVAILABLE: fewer than 10 valid frames; raw capture saved.")
        return 2
    median=statistics.median(intervals)
    p95=sorted(intervals)[int((len(intervals)-1)*0.95)]
    mean=statistics.mean(intervals)
    values={"label":label,"package":package,"captured_at":datetime.now(timezone.utc).isoformat(),
            "layer":layer,"valid_intervals":len(intervals),
            "mean_presented_fps":round(1000/mean,2),
            "p50_present_interval_ms":round(median,3),"p95_present_interval_ms":round(p95,3),
            "slow_over_9ms_pct":round(100*sum(x>9 for x in intervals)/len(intervals),2),
            "slow_over_16_67ms_pct":round(100*sum(x>16.67 for x in intervals)/len(intervals),2)}
    (folder/(label+"-summary.json")).write_text(json.dumps(values,indent=2))
    with (folder/(label+"-intervals.csv")).open("w",newline="") as f:
        writer=csv.writer(f);writer.writerow(["presented_frame_interval_ms"])
        writer.writerows([[round(x,4)] for x in intervals])
    print(json.dumps(values,indent=2))
    print("Compare the same menu/canvas and gesture between .21 and .22.")
    return 0

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--label",required=True)
    ap.add_argument("--package",default="com.artcraft.vectorcraft.test")
    ap.add_argument("--seconds",type=int,default=15)
    ap.add_argument("--out",type=Path,default=Path("vectorcraft-fps-results"))
    args=ap.parse_args()
    raise SystemExit(collect(args.package,args.label,args.seconds,args.out))
