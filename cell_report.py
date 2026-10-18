#!/usr/bin/env python3
"""One-line-per-cell M1 vs S1 report: pass^1 (Wilson), paired gain (task-cluster bootstrap), exhaustion, utilisation, tokens ratio, cost.
Usage: python3 cell_report.py <m1-run-name> <s1-results.json> [B]"""
import json, math, statistics, collections, random, sys
from pathlib import Path
def wilson(k,n,z=1.96):
    p=k/n; den=1+z*z/n; c=(p+z*z/(2*n))/den; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den; return c-h,c+h
def report(m1name, s1path):
    m=json.load(open(f'tau2-bench/data/simulations/{m1name}/results.json'))['simulations']
    s=json.load(open(s1path))['simulations']
    B=None
    mt=collections.defaultdict(list); st=collections.defaultdict(list); util=[]; exh=ex_ok=fin_ok=fin_n=0
    for x in m:
        r=(x.get('reward_info') or {}).get('reward',0); mt[x['task_id']].append(r)
        ag=[q for q in x['messages'] if q['role']=='assistant' and q.get('raw_data')]
        bud=ag[-1]['raw_data']['transfer_testing_completion_budget']; B=bud['limit']; util.append(bud['spent']/B)
        e=any(((q.get('raw_data') or {}).get('transfer_testing_termination')=='budget_exhausted') for q in ag)
        if e: exh+=1; ex_ok+=r>=1
        else: fin_n+=1; fin_ok+=r>=1
    for x in s: st[x['task_id']].append((x.get('reward_info') or {}).get('reward',0))
    tasks=sorted(set(mt)&set(st)); gains=[statistics.mean(mt[t])-statistics.mean(st[t]) for t in tasks]
    random.seed(300); bs=sorted(statistics.mean(random.choices(gains,k=len(tasks))) for _ in range(2000))
    m_ok=sum(sum(v) for v in mt.values()); n=sum(len(v) for v in mt.values()); s_ok=sum(sum(v) for v in st.values()); ns=sum(len(v) for v in st.values())
    lo,hi=wilson(m_ok,n); slo,shi=wilson(s_ok,ns)
    tm=statistics.median(sum(q['usage']['completion_tokens'] for q in x['messages'] if q['role']=='assistant' and q.get('usage')) for x in m)
    ts=statistics.median(sum(q['usage']['completion_tokens'] for q in x['messages'] if q['role']=='assistant' and q.get('usage')) for x in s)
    cm=sum((x.get('agent_cost') or 0)+(x.get('user_cost') or 0) for x in m); cs=sum((x.get('agent_cost') or 0)+(x.get('user_cost') or 0) for x in s)
    print(f"{m1name}\n  M1 {m_ok/n:.1%} [{lo:.1%}, {hi:.1%}] | S1 {s_ok/ns:.1%} [{slo:.1%}, {shi:.1%}] | gain {statistics.mean(gains):+.1%} CI [{bs[50]:+.1%}, {bs[1949]:+.1%}]")
    print(f"  exhausted {exh}/{n} = {exh/n:.0%} | util median {statistics.median(util):.2f} | finished pass {fin_ok}/{fin_n} = {fin_ok/max(fin_n,1):.0%}; exhausted pass {ex_ok}/{exh} = {ex_ok/max(exh,1):.0%}")
    print(f"  tokens/ep median M1 {tm:.0f} vs S1 {ts:.0f} = {tm/ts:.1f}x | cost M1 ${cm:.2f} vs S1 ${cs:.2f} | B={B}")
if __name__=='__main__':
    report(sys.argv[1], sys.argv[2])
