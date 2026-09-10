"""Fit a unit-scale rigid landmark transform and report independent checks."""

import argparse
import json
from pathlib import Path

import numpy as np

from polycam import digest


def rigid_transform(source,target):
    source,target=np.asarray(source,float),np.asarray(target,float)
    if source.shape!=target.shape or source.ndim!=2 or source.shape[1]!=3 or len(source)<3:
        raise ValueError("At least three paired 3-D landmarks are required")
    if not np.isfinite(source).all() or not np.isfinite(target).all():
        raise ValueError("Landmarks must be finite")
    a,b=source-source.mean(0),target-target.mean(0)
    if np.linalg.matrix_rank(a)<2 or np.linalg.matrix_rank(b)<2:
        raise ValueError("Collinear landmarks cannot constrain a rigid transform")
    u,s,vt=np.linalg.svd(a.T@b)
    correction=np.eye(3);correction[2,2]=np.linalg.det(vt.T@u.T)
    rotation=vt.T@correction@u.T
    matrix=np.eye(4);matrix[:3,:3]=rotation;matrix[:3,3]=target.mean(0)-rotation@source.mean(0)
    return matrix


def summarize(rows):
    errors=np.array([row["error_m"] for row in rows])
    return {"count":len(rows),"median_m":float(np.median(errors)),"p95_m":float(np.percentile(errors,95)),
            "max_m":float(errors.max())} if len(rows) else {"count":0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.resolve()==args.spec.resolve():raise ValueError("Output must not overwrite the input specification")
    spec=json.loads(args.spec.read_text());landmarks=spec["landmarks"]
    for key in ("source_frame","target_frame"):
        if not isinstance(spec.get(key),str) or not spec[key].strip():raise ValueError(f"{key} must identify a coordinate frame")
    if len({row["id"] for row in landmarks})!=len(landmarks):raise ValueError("Duplicate landmark ID")
    for row in landmarks:
        if row["role"] not in {"fit","check"}:raise ValueError("Every landmark needs fit or check role")
        if not row.get("evidence"):raise ValueError("Every landmark needs an evidence reference")
        for field in ["source","target"]:
            value=np.asarray(row[field],float)
            if value.shape!=(3,) or not np.isfinite(value).all():raise ValueError("Landmarks must be finite 3-D points")
    fitting=[row for row in landmarks if row["role"]=="fit"]
    matrix=rigid_transform([row["source"] for row in fitting],[row["target"] for row in fitting])
    groups={"fit":[],"check":[]}
    for row in landmarks:
        residual=np.array(row["source"])@matrix[:3,:3].T+matrix[:3,3]-np.array(row["target"])
        groups[row["role"]].append({**row,"residual_m":residual.tolist(),"error_m":float(np.linalg.norm(residual))})
    result={"matrix":matrix.tolist(),"convention":"Row-major 4x4; source-to-target; column homogeneous points; metres; unit scale",
            "source_frame":spec["source_frame"],"target_frame":spec["target_frame"],
            "spec_sha256":digest(args.spec),"landmarks":groups,"fit":summarize(groups["fit"]),"check":summarize(groups["check"]),
            "status":"candidate; inspect check evidence before acceptance" if groups["check"] else "unvalidated fit; no independent checks supplied",
            "limits":"Declared check roles do not prove independence. Check frames/features must be withheld from fitting and tuning; inspect source correspondence and regional validity."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"output":str(args.output),"fit":result["fit"],"check":result["check"],"status":result["status"]}))


if __name__=="__main__":main()
