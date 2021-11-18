#!/usr/bin/env python

"""Converts text-based Met data to H5 files for use with ATS.

Usage: convert_met_to_h5.py MY_MET_DATA.txt

creates MY_MET_DATA.h5
"""

import numpy as np
import h5py
import matplotlib.pyplot as plt


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
    hf.create_dataset('T', data=dtxt[:,0])
    hf.create_dataset('precip', data=dtxt[:,7])
    hf.create_dataset('solar_rad', data=dtxt[:,3])
    hf.create_dataset('atm_down_rad', data=dtxt[:,2])
    
    hf.close()
        
    plt.plot(times_sec,dtxt[:,2])
    plt.show()

if __name__ == "__main__":
    import sys
    filename = sys.argv[-1]
    convert(filename)
