import numpy as np
from matplotlib import pyplot as plt
import colors
import column_data, parse_ats
import sys,os
import warnings

class Loader:
    def __init__(self, label, dirname, names=None, coefs=None):
        self.label = label
        if names is None:
            self.names = dict()
        else:
            self.names = names

        if coefs is None:
            self.coefs = dict()
        else:
            self.coefs = coefs
            
        self.dir = dirname
        self.keys, self.times, self.ds = parse_ats.readATS(self.dir, 'visdump_surface_data.h5')

    def surface_data(self, name):
        try:
            coef = self.coefs[name]
            print 'got a coef = ', coef
        except KeyError:
            coef = 1

        try:
            name = self.names[name]
        except KeyError:
            pass

        print name,coef
            
        return self.times, coef * parse_ats.getSurfaceData(self.keys, self.ds, name)

    def subsurface_data(self, name):
        try:
            coef = self.coefs[name]
        except KeyError:
            coef = 1

        try:
            name = self.names[name]
        except KeyError:
            pass

        cd = column_data.column_data([name,], self.keys, self.dir)
        return self.times, cd[0,0,:], coef * cd[-1,:,:]

    
def ax_shape(count):
    if count is 1:
        ax_shape = (1,1)
    elif count == 2:
        ax_shape = (1,2)
    elif count == 3:
        ax_shape = (1,3)
    elif count == 4:
        ax_shape = (2,2)
    elif count <= 6:
        ax_shape = (3,2)
    elif count <= 9:
        ax_shape = (3,3)        
    elif count <= 12:
        ax_shape = (4,3)        
    elif count <= 16:
        ax_shape = (4,4)
    return ax_shape
    


def plot_one(names, loader, axs, color, cmap, glyph):
    for i, name in enumerate(names):
        if name.startswith('surface'):
            try:
                t, ds = loader.surface_data(name)
            except KeyError:
                warnings.warn("%s: Data not found for name '%s'"%(loader.label, name))
            else:
                axs[i].plot(t[1:], ds[1:], '-'+glyph, color=color, label=loader.label)
        else:
            try:
                ts,z,d = loader.subsurface_data(name)
            except KeyError:
                warnings.warn("%s: Data not found for name '%s'"%(loader.label, name))
            else:
                cm = colors.cm_mapper(-3,len(ts)-1, cmap=cmap)
                for j,t in enumerate(ts):
                    axs[i].plot(d[j][:], z, color=cm(j), label=loader.label)


def plot(names, loaders):
    fig, axs = plt.subplots(*ax_shape(len(names)), squeeze=False)
    axs = [a for b in axs for a in b]

    if len(loaders) > 4:
        raise RuntimeError("Only four loaders supported -- add more colors!")
    colors = ['b', 'r', 'g', 'orange']
    cmaps = ['Blues', 'Reds', 'Greens', 'Oranges']
    glyphs = ['x', '+', '^', 'v']

    for loader, color, cmap, glyph in zip(loaders, colors, cmaps, glyphs):
        plot_one(names, loader, axs, color, cmap, glyph)
    for name,ax in zip(names, axs):
        if name.startswith("surface"):
            ax.set_xlabel("time [yr?]")
            ax.set_ylabel(name)
            ax.legend()
        else:
            ax.set_xlabel(name)
            ax.set_ylabel('z coordinate')

clm_names = {'temperature':'temperature_soil'}
ats_names = {'surface-qE_conducted_soil':'surface-total_energy_source'}
ats_coefs = {'surface-qE_conducted_soil':-1.e6,
             'mass_source':1./55000.}
clm_coefs = dict()

            
if __name__ == "__main__":
    run = sys.argv[-1]

    names = ['temperature', 'surface-snow_depth', 'surface-qE_lw_out',
             'surface-qE_latent_heat', 'surface-qE_sensible_heat', 'surface-qE_conducted_soil',
             'surface-albedo', 'surface-mass_source', 'mass_source']

    dirname_ats = 'run-seb-ats'+run
    loader_ats = Loader('ATS', dirname_ats, ats_names, ats_coefs)
    dirname_clm = 'run-seb-clm'+run
    loader_clm = Loader('CLM', dirname_clm, clm_names, clm_coefs)

    plot(names, [loader_ats, loader_clm])
    plt.show()
    
