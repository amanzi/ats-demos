import h5py
import numpy as np

d = h5py.File("checkpoint04000.h5",'r')
d2 = h5py.File("ss_flow_results.h5",'w')
d2.create_dataset("time", data=np.array([0.,]))
flux = d2.create_group("surface-mass_flux.face.0")
pd = d2.create_group("ponded_depth.cell.0")
flux.create_dataset("0", data=d['surface-mass_flux.face.0'][:])
pd.create_dataset("0", data=d['ponded_depth.cell.0'][:])

d.close()
d2.close()
