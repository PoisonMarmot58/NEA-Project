"""Temporary calibration helper script."""

import json, numpy as np
from pathlib import Path
from scipy.ndimage import distance_transform_edt

root=Path(r"c:/Users/isaac/OneDrive/Desktop/NEA Project new/NEA-Project-2")
ports=json.loads((root/'src/pathfinder/data/ports_remapped_izmir.json').read_text(encoding='utf-8-sig'))
grid=np.load(root/'Pathfinder Algorithm/Data/FullGridOfEurope.npy')
H,W=grid.shape
water=(grid==0)
land=(grid==1)|(grid==2)
coast=np.zeros_like(water, dtype=bool)
for dr,dc in [(-1,0),(1,0),(0,-1),(0,1)]:
    ws=np.roll(np.roll(water,dr,0),dc,1)
    ls=np.roll(np.roll(land,dr,0),dc,1)
    coast |= (land & ws) | (water & ls)
coast[0,:]=coast[-1,:]=coast[:,0]=coast[:,-1]=False
dist=distance_transform_edt(~coast)
lats=np.array([p['latitude'] for p in ports],float)
lons=np.array([p['longitude'] for p in ports],float)

rng=np.random.default_rng(7)

def score(params):
    lat_min, lat_max, lon_min, lon_max=params
    rows=(lat_max-lats)/(lat_max-lat_min)*(H-1)
    cols=(lons-lon_min)/(lon_max-lon_min)*(W-1)
    out=((rows<0)|(rows>=H)|(cols<0)|(cols>=W)).sum()
    rr=np.clip(np.round(rows).astype(int),0,H-1)
    cc=np.clip(np.round(cols).astype(int),0,W-1)
    return float(np.mean(dist[rr,cc]+np.where(water[rr,cc],0,8))+out*200)

best=None; best_s=1e18
for _ in range(3000):
    lat_min=rng.uniform(22,36)
    lat_max=rng.uniform(64,80)
    if lat_max-lat_min<20: continue
    lon_min=rng.uniform(-30,-8)
    lon_max=rng.uniform(30,50)
    if lon_max-lon_min<30: continue
    s=score((lat_min,lat_max,lon_min,lon_max))
    if s<best_s:
        best_s=s; best=(lat_min,lat_max,lon_min,lon_max)

print('BEST',best,'SCORE',best_s)
lat_min,lat_max,lon_min,lon_max=best
for nm in ['Izmir','Piraeus','Felixstowe','Lisbon','Rotterdam','Constanta','Hamburg']:
    p=next(pp for pp in ports if pp['name']==nm)
    r=(lat_max-p['latitude'])/(lat_max-lat_min)*(H-1)
    c=(p['longitude']-lon_min)/(lon_max-lon_min)*(W-1)
    rr,cc=int(round(r)),int(round(c))
    rr=max(0,min(H-1,rr)); cc=max(0,min(W-1,cc))
    print(nm,rr,cc,'dist',float(dist[rr,cc]),'water',bool(water[rr,cc]))
