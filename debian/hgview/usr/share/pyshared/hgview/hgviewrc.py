"""
Manages hgview's config
"""
import os
import imp
import traceback

HGVIEWRC = '.hgviewrc'

DEFAULT_CONFIG = {
    'windowsize' : (800,600),
    'windowpos' : (0,0),
    }

def get_home_dir():
    """return the path to the home directory of the current user"""
    return os.path.expanduser('~')

def get_hgviewrc_names( repo_dir=None ):
    """"return the paths of candidate hgview config files"""
    if repo_dir is not None:
        yield os.path.join( repo_dir, HGVIEWRC )
    yield os.path.join( get_home_dir(), HGVIEWRC )

def get_hgviewrc( repo_dir=None ):
    """"return the paths of readable hgview config files"""
    for rc_file in  get_hgviewrc_names( repo_dir ):
        if  os.access( rc_file, os.R_OK ):
            yield rc_file

def load_config( fname, config ):
    """update the config dictionary with value found in the file found at
    <fname> path"""
    try:
        config_file = file(fname)
        mod = imp.load_module( "config", config_file, fname,
            ('', 'r', imp.PY_SOURCE) )
        cfg = {}
        for key, value in mod.__dict__.items():
            if not key.startswith('_'):
                cfg[key] = value
        config.update( cfg )
    except Exception : # pylint: disable-msg=W0703
        print "Couldn't read config file:", fname
        traceback.print_exc()

def write_config( fwhere, config ):
    """write the dictionary content into a file found ar <fwhere> path
    erase any existing file"""
    target_file = file( fwhere, 'w' )
    target_file.write( "# file generate by hgview.hgviewrc\n" )
    target_file.writelines( "%s = %r\n" % item for item in config.iteritems() )

def read_config( repo_dir=None ):
    """build config for the repository found at <repo_dir>"""
    config = DEFAULT_CONFIG.copy()
    for rc_file in get_hgviewrc(repo_dir):
        load_config(rc_file, config)
    return config


class Config(object):
    """Object handling multiple hgview config source"""
    __WHERE = ('repo', 'home', 'default')
    def __init__(self):
        self._configs = [ {}, {}, DEFAULT_CONFIG ]

    def load_configs(self, repo_dir):
        """update the current config with the config file found in the repo"""
        frepo, fhome = get_hgviewrc_names( repo_dir )
        load_config( fhome, self._configs[1] )
        load_config( frepo, self._configs[0] )

    def save_configs(self, repo_dir):
        """write the current config in the repo"""
        frepo, fhome = get_hgviewrc_names( repo_dir )
        write_config( fhome, self._configs[1] )
        write_config( frepo, self._configs[0] )

    def __getattr__(self, name):
        """return value of option if exist"""
        for source in self._configs:
            if name in source:
                return source[name]
        raise AttributeError('unknown config option %s' % name )

    def __setattr__(self, name, value):
        """Setattr only works on existing values"""
        if name.startswith("_"):
            self.__dict__[name] = value
            return
        for source in self._configs:
            if name in source:
                source[name] = value
                return
        raise AttributeError('unknown config option %s' % name )

    def set_in_repo(self, name, value):
        """add or update an option in the repo config"""
        self._configs[0][name] = value

    def set_in_home(self, name, value):
        """add or update an option in the user config"""
        self._configs[1][name] = value

    def keys(self):
        """return the name of all define option"""
        all_keys = set()
        for source in self._configs:
            all_keys.update( source.iterkeys() )
        return list(all_keys)

    def where(self, option):
        """return the location where an option is defined:
        possible value: "repo", "home", "default", None"""
        for idx, source in enumerate(self._configs):
            if option in source:
                return self.__WHERE[idx]
                
    def dump(self):
        """print key, value, source for all option"""
        for option in self.keys():
            print option, getattr(self, option), self.where(option)
            
if __name__ == "__main__":
    # pylint: disable-msg=C0103
    print "Home dir:", get_home_dir()
    print "hgviewrc:", get_hgviewrc_names( os.getcwd() )
    print "hgviewrc:", ', '.join(get_hgviewrc( os.getcwd() ))
    current_config = Config()
    current_config.load_configs( os.getcwd() )
    current_config.dump()

