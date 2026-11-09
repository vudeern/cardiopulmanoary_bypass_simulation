"""Retain all selected witness commands for independent full-plant replay."""
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from slowdown_audit import OUT,ROOT,patient,scenario,PLANTS
from perfusion_lab.audit import witness
from simc_benchmark import digest,dumps


def one(item):
 key,v=item
 w=witness(patient(v['seed'],'evaluation'),scenario(v['phys']),PLANTS[v['plant']],oxygen_cap=v['selected']=='oxygen_capped')
 assert w['feasible']==v['feasible']
 for k,value in v['metrics'].items():assert abs(w['metrics'][k]-value)<1e-8
 return key,[r['command'] for r in w['rows']]


if __name__=='__main__':
 bench=json.loads((OUT/'benchmarks.json').read_text());commands={}
 with ProcessPoolExecutor(max_workers=4,mp_context=get_context('spawn')) as pool:
  for key,values in pool.map(one,bench.items()):commands[key]=values
 result=dict(benchmark_sha256=digest(OUT/'benchmarks.json'),generator_sha256=digest(Path(__file__)),commands=commands)
 (OUT/'witness-commands.json').write_text(dumps(result));print('Retained 96 full witness command schedules; each matches the frozen benchmark.')
