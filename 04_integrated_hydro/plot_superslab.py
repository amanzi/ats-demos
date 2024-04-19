import pandas as pd
import os
from matplotlib import pyplot as plt
import numpy as np
import ats_xdmf

#dirnames = ['superslab.demo-smooth_0', 'superslab.demo-smooth_001', 'superslab.demo-smooth_005', 'superslab.demo-smooth_01']
#labels = ['kr_sm=0', 'kr_sm=0.01', 'kr_sm=0.05', 'kr_sm=0.1']

#dirnames = ['superslab.demo-tpfa', 'superslab.demo-mfd_so', 'superslab.demo-mfd_monohex', ]
#labels = ['TPFA', 'support operator', 'mfd: hex']

dirnames = ['superslab.demo', '/home/ecoon/code/ats/ats/repos/master/src/physics/ats/docs/documentation/source/ats_demos/04_integrated_hydro/superslab.demo']
labels = ['ats-1.4', 'master']

colors = ['b', 'r', 'g', 'orange', 'goldenrod']

fig,ax = plt.subplots(3,2)
molar_dens = 55347.3783

def plot(dirname, color, label):
    df = pd.read_csv(os.path.join(dirname, 'observations.dat'), comment='#')
    vis = ats_xdmf.VisFile(dirname)
    vis.loadMesh(columnar=True)

    sat = vis.getArray('saturation_liquid')
    wc = vis.getArray('water_content')
    print(sat.shape)
    

    ss = np.where(sat >= 1.0, wc, 0.).sum(-1).sum(-1) / molar_dens
    uss = np.where(sat >= 1.0, 0., wc).sum(-1).sum(-1) / molar_dens
    vtimes = vis.times/3600
    print(vtimes.shape)

    ax[0,0].plot(vtimes, ss, color=color, label=label)
    ax[0,1].plot(vtimes, uss, color=color, label=label)

    ax[1,0].plot(df['time [h]'], df['surface storage [mol]'] / molar_dens, color=color, label=label)
    ax[1,1].plot(df['time [h]'], df['outlet discharge [mol (ten minutes)^-1]'] / molar_dens * 6, color=color, label=label)

    ax[2,0].plot(df['time [h]'], df['slab 1 flux [mol (ten minutes)^-1]'] / molar_dens * 6, color=color, label=label)
    ax[2,1].plot(df['time [h]'], df['slab 2 flux [mol (ten minutes)^-1]'] / molar_dens * 6, color=color, label=label)
    
    return df

for arg in zip(dirnames, colors, labels):
    df = plot(*arg)

ax[0,0].set_ylabel('saturated storage [m^3]')
ax[0,0].set_xlabel('time [h]')
ax[0,0].set_ylim([0,20])
ax[0,1].set_ylabel('unsaturated storage [m^3]')
ax[0,1].set_xlabel('time [h]')
ax[0,1].set_ylim([0,40])

ax[1,0].set_ylabel('ponded storage [m^3]')
ax[1,0].set_xlabel('time [h]')
ax[1,0].set_ylim([0,8e-3])
ax[1,1].set_ylabel('outlet discharge [m^3/h]')
ax[1,1].set_xlabel('time [h]')
ax[1,1].set_ylim([0,0.8])


ax[2,0].set_ylabel('slab 1 discharge [m^3/h]')
ax[2,0].set_xlabel('time [h]')
ax[2,0].set_ylim([0,1.4e-7])
ax[2,1].set_ylabel('slab 2 discharge [m^3/h]')
ax[2,1].set_xlabel('time [h]')
ax[2,1].set_ylim([0,1])

ax[2,1].legend()

plt.show()
