"""
Manages hgview's config
"""
import os
import imp
from ConfigParser import SafeConfigParser

HGVIEWRC = '.hgviewrc'

DEFAULT_CONFIG = {
    'windowsize' : (800,600),
    'windowpos' : (0,0),
    }

def get_home_dir():
    return os.path.expanduser('~')

def get_hgviewrc_names( repo_dir ):
    frepo = os.path.join( repo_dir, HGVIEWRC )
    fhome = os.path.join( get_home_dir(), HGVIEWRC )
    return frepo, fhome

def get_hgviewrc( repo_dir ):
    frepo, fhome = get_hgviewrc_names( repo_dir )
    if not os.access( frepo, os.R_OK ):
        frepo = None
    if not os.access( fhome, os.R_OK ):
        fhome = None
    return frepo, fhome

def load_config( fname, config ):
    try:
        f = file(fname)
        mod = imp.load_module( "config", f, fname, ('','r', imp.PY_SOURCE) )
        cfg = {}
        for k,v in mod.__dict__.items():
            if not k.startswith('_'):
                cfg[k] = v
        config.update( cfg )
    except :
        import traceback
        print "Couldn't read config file:", fname
        #traceback.print_exc()

def write_config( fwhere, config ):
    f = file( fwhere, 'w' )
    f.write( "# generated file" )
    for k, v in config.items():
        f.write( "%s = %r\n" % (k,v) )

def read_config( repo_dir ):
    frepo, fhome = get_hgviewrc_names( repo_dir )
    config = DEFAULT_CONFIG.copy()
    return config


class Config(object):
    def __init__(self):
        self._configs = [ {}, {}, DEFAULT_CONFIG ]

    def load_configs(self, repo_dir):
        frepo, fhome = get_hgviewrc_names( repo_dir )
        load_config( fhome, self._configs[1] )
        load_config( frepo, self._configs[0] )

    def save_configs(self, repo_dir):
        frepo, fhome = get_hgviewrc_names( repo_dir )
        write_config( fhome, self._configs[1] )
        write_config( frepo, self._configs[0] )

    def __getattr__(self, name):
        for c in self._configs:
            if name in c:
                return c[name]
        raise AttributeError('unknown config option %s' % name )

    def __setattr__(self, name, value):
        """Setattr only works on existing values"""
        if name.startswith("_"):
            self.__dict__[name] = value
            return
        for c in self._configs:
            if name in c:
                c[name] = value
                return
        raise AttributeError('unknown config option %s' % name )

    def set_in_repo(self, name, value):
        self._configs[0][name] = value

    def set_in_home(self, name, value):
        self._configs[1][name] = value

    def keys(self):
        s = set()
        for c in self._configs:
            s.update( c.keys() )
        return list(s)

    def where(self, k):
        WHERE = ['repo','home','default']
        for i,c in enumerate(self._configs):
            if k in c:
                return WHERE[i]
                
    def dump(self):
        for k in self.keys():
            print k, getattr(self,k), self.where(k)
            
if __name__ == "__main__":
    print "Home dir:", get_home_dir()
    print "hgviewrc:", get_hgviewrc_names( os.getcwd() )
    print "hgviewrc:", get_hgviewrc( os.getcwd() )
    config = Config()
    config.load_configs( os.getcwd() )
    config.dump()

