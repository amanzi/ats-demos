"""Class for reading with ATS hdf5 files"""

import h5py

class File(object):
    def __init__(self, fname, access='r'):
        self._fid = h5py.File(fname,access)
        try:
            self._keys = sorted(self._fid[self._fid.keys()[0]].keys(), lambda a,b: int.__cmp__(int(a),int(b)))
        except Error:
            self._keys = None

        self._vars = self._fid.keys()

    def close(self):
        self._fid.close()

    def __getitem__(self, index):
        return self._fid.__getitem__(index)

    def simulationTime(self):
        raise NotImplementedError("simulation time not implemented")

    def numSteps(self):
        if self._keys is None:
            return None
        else:
            return int(self._keys[-1])

    def matches(self, varname):
        if '.' in varname and varname in self._vars:
            return [varname,]
        else:
            return [v for v in self._vars if v.startswith(varname)]

    def steps(self):
        return self._keys


        
