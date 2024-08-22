#!/usr/bin/env python

"""Converts text-based Met data to H5 files for use with ATS.

Usage: convert_met_to_h5.py MY_MET_DATA.txt

creates MY_MET_DATA.h5
"""

import numpy as np
import h5py
import matplotlib.pyplot as plt

fig_pre = plt.figure()
ax_fig_pre = fig_pre.add_subplot(1,1,1)

fig_temp = plt.figure()
ax_fig_temp = fig_temp.add_subplot(1,1,1)

fig_solar_rad = plt.figure()
ax_fig_solar_rad = fig_solar_rad.add_subplot(1,1,1)

fig_pressure = plt.figure()
ax_fig_pressure = fig_pressure.add_subplot(1,1,1)

fig_hum = plt.figure()
ax_fig_hum = fig_hum.add_subplot(1,1,1)

def convert(filename):
            
    # grab data
    dtxt = np.loadtxt(filename,delimiter=",")
    
    print(filename)
    print(dtxt.shape[0])
    print(dtxt.shape[1])

    # turn into hdf5
    h5filename = filename[:-4]+".h5"
    hf = h5py.File(h5filename, 'w')
    times_days = np.arange(dtxt.shape[0])
    times_sec = times_days[:]*24.*3600.
    hf.create_dataset('time', data=times_sec)
    hf.create_dataset('T_air', data=dtxt[:,0])
    hf.create_dataset('pres', data=dtxt[:,1])
    hf.create_dataset('atm_down_rad', data=dtxt[:,2])
    hf.create_dataset('solar_rad', data=dtxt[:,3])
    hf.create_dataset('hum_air', data=dtxt[:,6])
    hf.create_dataset('precip', data=dtxt[:,7])

    
    hf.close()

    ax_fig_temp.plot(times_days,dtxt[:,0])
    ax_fig_pressure.plot(times_days,dtxt[:,1])
    ax_fig_solar_rad.plot(times_days,dtxt[:,3])
    ax_fig_hum.plot(times_days,dtxt[:,6])
    ax_fig_pre.plot(times_days,dtxt[:,7])
#    plt.show()


    fig_pre.savefig("precip_data.pdf",format="pdf")
    fig_temp.savefig("temp_air_data.pdf",format="pdf")
    fig_solar_rad.savefig("solar_rad_data.pdf",format="pdf")
    fig_pressure.savefig("pressure_data.pdf",format="pdf")
    fig_hum.savefig("humidity_data.pdf",format="pdf")

if __name__ == "__main__":
    import sys
    filename = sys.argv[-1]
    convert(filename)
