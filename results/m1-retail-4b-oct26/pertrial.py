import json,statistics as st,collections,sys
R=sys.argv[1]
d=json.load(open(R))
MA="transfer_testing_multi_agent";TERM="transfer_testing_termination"
sims=d["simulations"]
def exh(s): return any(((m.get("raw_data") or {}).get(TERM)=="budget_exhausted") for m in s["messages"] if m["role"]=="assistant")
for t in sorted({s["trial"] for s in sims}):
    ss=[s for s in sims if s["trial"]==t]
    by=collections.defaultdict(list);cut=collections.Counter();emp=collections.Counter();tot=0;cuttok=0;dc=[];turns=[]
    for s in ss:
        n=0
        for i,m in enumerate(s["messages"]):
            if m["role"]!="assistant": continue
            rd=m.get("raw_data") or {}
            if MA not in rd: continue
            n+=1; nc=0
            for c in rd[MA]["components"]:
                ct=(c.get("usage") or {}).get("completion_tokens",0) or 0
                by[c["call_name"]].append(ct); tot+=ct
                if c.get("truncated"): cut[c["call_name"]]+=1; cuttok+=ct; nc+=1
                if c["call_name"] in ("m1_plan","m1_act","m1_forced_message") and not c.get("output"): emp[c["call_name"]]+=1
            if nc>=2: dc.append(rd.get(TERM))
        turns.append(n)
    print(f"trial {t} seed {ss[0]['seed']}: eps {len(ss)} exhausted {sum(exh(s) for s in ss)} turns/ep {st.mean(turns):.1f} cut-token share {cuttok/tot:.1%} double-cut {len(dc)} {collections.Counter(dc)}")
    for k in ("m1_plan","m1_forced_message","m1_act","m1_db_read","m1_db_write","m1_advisor"):
        v=by.get(k,[])
        if v: print(f"   {k:18s} n={len(v):4d} median={st.median(v):5.0f} cut={cut[k]:3d} empty={emp[k]}")
