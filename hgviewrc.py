"""
Manages hgview's config
"""
import os
import imp
from ConfigParser import SafeConfigParser

HGVIEWRC = '.hgviewrc'

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
    config = {}
    load_config( fhome, config )
    load_config( frepo, config )
    return config


if __name__ == "__main__":
    print "Home dir:", get_home_dir()
    print "hgviewrc:", get_hgviewrc_names( os.getcwd() )
    print "hgviewrc:", get_hgviewrc( os.getcwd() )
    print "config:", read_config( os.getcwd() )
