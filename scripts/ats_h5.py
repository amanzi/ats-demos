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

    def __exit__(self):
        return self.close()

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
            matches = []
            for v in self._vars:
                if v.split('.')[0] == varname:
                    matches.append(v)
                else:
                    # this deals with the changing names from
                    # ponded_depth to surface-ponded_depth, etc
                    vsplit = v.split('.')[0].split('-')
                    varnamesplit = varname.split('.')[0].split('-')
                    if vsplit[-1] == varnamesplit[-1] and \
                       len(vsplit) == 2 and vsplit[0] == 'surface' and \
                       len(varnamesplit) == 1:
                        matches.append(v)
                    
            return matches

    def steps(self):
        return self._keys


        
