import json, urllib.request, urllib.error
from pathlib import Path
import os, subprocess

def az(*args):
 result = subprocess.run(['az',*args,'--only-show-errors','-o','json'],capture_output=True,text=True,check=True)
 return json.loads(result.stdout)
rg, app = os.environ['RG'], os.environ['APP']
api = az('containerapp','show','-g',rg,'-n',app+'-api')
base='https://'+api['properties']['configuration']['ingress']['fqdn']
secrets=az('containerapp','secret','list','-g',rg,'-n',app+'-frontend','--show-values')
token=next(s['value'] for s in secrets if s['name']=='api-token')
headers={'Authorization':'Bearer '+token,'X-User-Id':'palmw01','Content-Type':'application/json'}
def call(path,body=None):
 req=urllib.request.Request(base+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
 with urllib.request.urlopen(req,timeout=40) as r: return json.load(r)
c=call('/v1/annotatie/capabilities'); assert c['schema_versie']==int(os.environ['CONTRACT']); print('Contract bevestigd:',c['schema_versie'])
if c['schema_versie']==1: raise SystemExit(0)
v=call('/v1/annotatie/weergave?bwb_id=BWBR0004770&artikel=9&lid=1')
print('Doel',json.dumps(v['doel'],ensure_ascii=False))
assert v['segmenten'] and all(s['bron_iri']=='urn:bwb:BWBR0004770:artikel:9:lid:1' for s in v['segmenten'])
print('Alleen lid 1:',len(v['segmenten']),'segment(en)')
assert not v['elementen']; print('Geen annotaties overgebleven')
x=call('/v1/annotatie/weergave/export',{'bron_iri':'urn:bwb:BWBR0004770:artikel:9:lid:1','snapshot_id':v['snapshot_id'],'formaat':'json'})
assert x['segmenten']==v['segmenten'];print('Export behoudt lidselectie')
r=call('/v1/annotatie/zoeken',{'bron_iri':'urn:bwb:BWBR0004770:artikel:9:lid:1','tekst':'belasting'})
print('Graafzoektool:',json.dumps(r,ensure_ascii=False)[:700])
try:
 call('/v1/annotatie/documenten',{})
 raise AssertionError('Oude schrijfroute onverwacht toegestaan')
except urllib.error.HTTPError as ex:
 assert ex.code==409,(ex.code,ex.read().decode())
 print('Oude artikelbrede schrijfroute: 409, correct geweigerd')
print('LIVE_SMOKE_OK')
