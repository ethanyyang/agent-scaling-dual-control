import os as _os, sys as _sys
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_HERE = _os.path.dirname(_os.path.abspath(__file__))
import json,statistics,collections,random,math,sys,os
S=_REPO + "/tau2-bench/data/simulations/"
def load(n): return json.load(open(S+n+"/results.json"))['simulations']
def rw(x): return (x.get('reward_info') or {}).get('reward',0) or 0
def tok(x): return sum(q['usage']['completion_tokens'] for q in x['messages'] if q['role']=='assistant' and q.get('usage'))
def cost(xs): return sum((x.get('agent_cost') or 0)+(x.get('user_cost') or 0) for x in xs)
def label(x):
    l='normal'
    for m in x['messages']:
        rd=m.get('raw_data') or {}
        if rd.get('transfer_testing_termination'): l=rd['transfer_testing_termination']
    return l
def wilson(k,n,z=1.96):
    p=k/n; den=1+z*z/n; c=(p+z*z/(2*n))/den; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den; return c-h,c+h
def bytask(xs):
    d=collections.defaultdict(list)
    for x in xs: d[x['task_id']].append(rw(x))
    return {t:statistics.mean(v) for t,v in d.items()}
def boot(vals):
    random.seed(300); bs=sorted(statistics.mean(random.choices(vals,k=len(vals))) for _ in range(2000)); return statistics.mean(vals),bs[50],bs[1949]
def gain(a,b):
    ta,tb=bytask(a),bytask(b); ts=sorted(set(ta)&set(tb)); return {t:ta[t]-tb[t] for t in ts}
def dd(g1,g2):
    ts=sorted(set(g1)&set(g2)); return [g1[t]-g2[t] for t in ts]
def desc(lab,xs):
    k=sum(rw(x) for x in xs); n=len(xs); lo,hi=wilson(k,n); ex=sum(1 for x in xs if label(x)=='budget_exhausted')
    return f"{lab:14s} {k/n:.1%} [{lo:.1%}, {hi:.1%}] n={n} exhausted {ex} tokens/ep median {statistics.median(tok(x) for x in xs):.0f} cost ${cost(xs):.2f}"
def fmt(t): return f"{t[0]:+.1%} [{t[1]:+.1%}, {t[2]:+.1%}]"
