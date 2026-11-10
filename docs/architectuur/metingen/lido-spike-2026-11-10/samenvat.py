import json,sys,collections,statistics
d=json.load(open(sys.argv[1])); A=d['artikelen']
print('stat',d['stat'],'artikelen',len(A))
mis=[a['artikel'] for a in A if not a['versies']]; print('zonder LiDO-id',len(mis),mis[:20])
lab=[a for a in A if a['versies'] and a['label_id_lido']!=[a['label_id_bwb']]]; print('label-id wijkt af',len(lab),[(a['artikel'],a['label_id_bwb'],a['label_id_lido']) for a in lab][:5])
nv=[len(a['versies']) for a in A if a['versies']]; print('versies: med',statistics.median(nv),'max',max(nv),'som',sum(nv))
ecli=lambda u:u.rstrip('/').split('/')[-1]
def juris(a,alleen_huidig=False):
    vs=a['versies'][:1] if alleen_huidig else a['versies']
    return {ecli(l['doel']) for l in a['links'] if l['groep']=='Jurisprudentie' and l['richting']=='inkomende' and l['versie'] in vs}
tot=[len(juris(a)) for a in A]; hu=[len(juris(a,True)) for a in A]
print('uitspraken over versies: paren',sum(tot),'unieke ECLI',len(set().union(*[juris(a) for a in A])),'artikelen met >=1',sum(1 for x in tot if x),'mediaan',statistics.median(tot),'max',max(tot))
print('alleen huidige versie: paren',sum(hu),'artikelen met >=1',sum(1 for x in hu if x), 'aandeel van totaal', round(sum(hu)/max(1,sum(tot)),2))
top=sorted(A,key=lambda a:-len(juris(a)))[:12]; print('top (art, alle, huidig)',[(a['artikel'],len(juris(a)),len(juris(a,True))) for a in top])
lt=collections.Counter((l['richting'],l['groep'],l['label']) for a in A for l in a['links'])
for k,v in lt.most_common(25): print(' ',v,k)
inst=collections.Counter(e.split(':')[2] for a in A for e in juris(a))
print('instanties',inst.most_common(15))
jr=collections.Counter(e.split(':')[3] for a in A for e in juris(a)); print('jaren',sorted(jr.items()))
ext=collections.Counter(l['titel'].split(',')[0] for a in A for l in a['links'] if l['groep'] not in ('Jurisprudentie','Officiele overheidspublicatie') and l['richting']=='inkomende')
print('inkomende regelingen: soorten',len(ext),ext.most_common(10))
print('kst-links',sum(1 for a in A for l in a['links'] if '/kst-' in (l['doel'] or '')))
