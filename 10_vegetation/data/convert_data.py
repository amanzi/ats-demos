import sys,os
sys.path.append(os.path.join(os.environ['ATS_SRC_DIR'],'tools','utils'))

import h5py
import numpy as np
import parse_xmf

cycles, times, dat = parse_xmf.readATS("/lclscratch/ats/1D-Column/INPUT-FILES/Joel-Staked-Spinup-10cmPeat")
times = np.array(times)
cycles = np.array(cycles)
inds = np.where(times >= 9.0)[0]
inds = inds[::7]

times = times[inds]
# convert to seconds, start at 0
times = (times-9.)*86400*365.25
cycles = cycles[inds]

with h5py.File("soil_temp_sat.h5",'a') as fid:
    fid.create_dataset("time",data=times)

    g = fid.create_group("temperature.cell.0")
    for i,cycle in enumerate(cycles):
        g.create_dataset(str(i), data=dat["temperature.cell.0"][cycle][:])

    g = fid.create_group("pressure.cell.0")
    for i,cycle in enumerate(cycles):
        g.create_dataset(str(i), data=dat["pressure.cell.0"][cycle][:])
        
dat.close()

