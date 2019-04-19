import h5py
import numpy as np
import matplotlib.pyplot as plt

with h5py.File('test2.h5', 'r') as f_in:
    time = f_in.get("Time")
    flux = f_in.get("Flux")
    head = f_in.get("Head")

    # for i in range(1,10):
    #     print time[217-i], flux[217-i], time[217+i-1], flux[217+i-1]  
    
    plt.plot(time, head)
    plt.xlim([0, 2*86400])
    plt.show()
