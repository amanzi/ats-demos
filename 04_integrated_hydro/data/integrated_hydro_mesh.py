"""
Example of using meshing_ats.py to generate a simple hillslope.

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
    sys.path.append(os.path.join(os.environ['ATS_SRC_DIR'],'tools','meshing_ats'))
    import meshing_ats

def make_mesh(dx, dz, slope, fname):
    # set up the surface mesh, a strip of cells
    x_max = 400.0
    n_x = int(np.round(x_max / dx))

    x = np.linspace(0.0, x_max, n_x + 1)
    z = -slope * x

    # make 2D mesh
    m2 = meshing_ats.Mesh2D.from_Transect(x,z,80)

    # make 3D mesh, extruding in a fixed approach
    # layer extrusion
    soil_thickness = 5.0
    nz = int(np.round(soil_thickness / dz))

    # -- data structures needed for extrusion
    layer_types = ['constant']
    layer_data = [soil_thickness]
    layer_ncells = [nz]
    layer_mat_ids = [101]

    m3 = meshing_ats.Mesh3D.extruded_Mesh2D(m2, layer_types, 
                                            layer_data, 
                                            layer_ncells, 
                                            layer_mat_ids)
    m3.write_exodus(fname)


make_mesh(80.0, 0.2, 0.0005, 'hillslope.exo')
make_mesh(80.0, 0.2, 0.05, 'hillslope_steep.exo')

make_mesh(10., 0.05, 0.0005, 'hillslope_hires.exo')
make_mesh(10., 0.05, 0.05, 'hillslope_steep_hires.exo')
