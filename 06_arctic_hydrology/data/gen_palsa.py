"""
Example of using meshing_ats.py to generate a very simple 2D mesh
with layers, variable resolution, and varying topography.
"""

import sys,os
import numpy as np
from matplotlib import pyplot as plt

# This is the standard path for SEACAS if Amanzi TPLS are built via
# bootstrap with --build-shared
try:
    import exodus
except ImportError:
    sys.path.append(os.path.join(os.environ['AMANZI_TPLS_DIR'],'SEACAS', 'lib'))
    import exodus

# This is the standard path for ATS's source directory    
try:
    import meshing_ats
except ImportError:
    sys.path.append(os.path.join(os.environ['ATS_SRC_DIR'],'tools','meshing_ats','meshing_ats'))
    import meshing_ats

# set up the surface mesh
# -- generate some topography
x = np.linspace(-50.0, 50.0, 21)
z = 5. - np.cos(np.pi/100. * x)**2

plt.plot(x,z)
plt.show()

# -- using from_Transect extrudes the x,z line in the y-direction to
#    create 1 cell in y.  This results in a transect across our
#    topography
m2 = meshing_ats.Mesh2D.from_Transect(x,z)

# layer extrusion
# -- data structures needed for extrusion
layer_types = []
layer_data = []
layer_ncells = []
layer_mat_ids = []
z = 0.0

# -- peat layer --
#  top 20 cm
#  2 cm per grid cell
#  10 cells
layer_types.append("constant")
layer_data.append(0.2)
layer_ncells.append(10)
layer_mat_ids.append(1001)
z += 0.2

# -- mineral layer part 1 --
#  next 80 cm
#  2 cm per grid cell
#  40 cells
layer_types.append("constant")
layer_data.append(0.8)
layer_ncells.append(40)
layer_mat_ids.append(1002)
z += 0.8

# -- mineral layer part 2 --
#  15 cells
#  expanding dz, growing with depth
ncells = 15
dz = 0.02
for i in range(ncells):
    dz *= 1.2
    layer_types.append("constant")
    layer_data.append(dz)
    layer_ncells.append(1)
    layer_mat_ids.append(1002)
    z += dz

# -- mineral layer part 3 --
#  keep expanding until we hit 2m
#  expanding dz, growing with depth
dz *= 2
while dz < 1.5:
    layer_types.append("constant")
    layer_data.append(dz)
    layer_ncells.append(1)
    layer_mat_ids.append(1002)
    z += dz
    dz *= 2

# -- mineral layer part 4 --
# two cells to align the telescope to max it out at 2m,
# while still getting it to land on an even number and
# be reasonable.
dz = (10.0 - z) / 3.0
layer_types.append("constant")
layer_data.append(3*dz)
layer_ncells.append(3)
layer_mat_ids.append(1002)
z += 3*dz

# -- mineral layer part 5 --
# keep going for ~2m cells until we hit the bottom of
# the domain
layer_types.append("snapped")
layer_data.append(-40) # depth of bottom of domain is 40 m
layer_ncells.append(int(round((-layer_data[-1]-z) / 2.0)))
layer_mat_ids.append(1002)

# -- print out a summary --
# count = 0
# print "Cell summary:"
# print "--------------------------------------"
# print "l_id| c_id| mat_id| dz"
# for i,thick in enumerate(layer_data):
#     for j in range(layer_ncells[i]):
#         print " %02i | %02i | %04i | %g"%(i,count,layer_mat_ids[i],thick/layer_ncells[i])
#         count += 1

# Extrude the 3D model with this structure and write to file
m3 = meshing_ats.Mesh3D.extruded_Mesh2D(m2, layer_types, 
                                        layer_data, 
                                        layer_ncells, 
                                        layer_mat_ids)
m3.write_exodus("palsa.exo")
