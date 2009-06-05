
from os.path import join, dirname, expanduser, pardir, abspath, exists
from os import unlink
from logilab.common.testlib import TestCase, unittest_main, with_tempdir
from ConfigParser import SafeConfigParser as ConfigParser
from tempfile import NamedTemporaryFile, TemporaryFile, mkdtemp
from shutil import copyfileobj

from hgviewlib import config

DATADIR= 'data'
def input_path(path=''):
    return abspath(join(dirname(__file__), DATADIR, path))

EXPECTED_FILE = """# file generate by hgqv.hgqvrc
answer = 42
bob = 'coin'
more_test = 'igloo'
"""


class LonelyFunctionTC(TestCase):


    def setUp(self):
        self.__rc_path = join(hgqvrc.get_home_dir(), hgqvrc.HGQVRC)
        if self.__rc_path in hgqvrc.get_hgqvrc():
            self.__rc_home = TemporaryFile()
            copyfileobj(open(self.__rc_path), self.__rc_home)
            unlink(self.__rc_path)
        else:
            self.__rc_home = None
    def tearDown(self):
        if self.__rc_home is not None:
            copyfileobj(self.__rc_home,open(self.__rc_path,"w"))
        elif exists(self.__rc_path):
            unlink(self.__rc_path)
        

    def test_load(self):
        config = {}
        hgqvrc.load_config(input_path('hgqvrc'), config)
        self.assertDictEquals(config, {'win':1, "truc":"toto"})
    @with_tempdir
    def test_write(self):
        temp_file = NamedTemporaryFile()
        config = {
            "answer":42,
            "bob":"coin",
            "more_test":"igloo"
        }
        hgqvrc.write_config(temp_file.name, config)
        temp_file.seek(0)


        self.assertTextEquals(temp_file.read(),EXPECTED_FILE)


    def  test_get_home_dir(self):
        self.assertEquals(hgqvrc.get_home_dir(), expanduser('~'))

    def test_get_hgqvrc_names(self):
        names = tuple(hgqvrc.get_hgqvrc_names( input_path(pardir) ))
        self.assertEquals( names[1], expanduser(join('~','.hgqvrc')))
        self.assertEquals( names[0], join(input_path(pardir),'.hgqvrc'))
    def test_get_hgqvrc_exist(self):
        names = hgqvrc.get_hgqvrc( input_path() )
        self.assert_( input_path('.hgqvrc') in names)
    
    def test_get_hgqvrc_do_not_exist(self):
        names = tuple(hgqvrc.get_hgqvrc( dirname(__file__) ))
        self.assert_( join(dirname(__file__), '.hgqvrc') not in names)

    def test_read_config_no_hgqvrc(self):
        #XXX: beware the ~/.hgqvrc file
        EXPECTED = hgqvrc.DEFAULT_CONFIG.copy()
        
        config = hgqvrc.read_config(dirname(__file__))

        self.assertDictEquals(config,EXPECTED)
    
    def test_read_config_hgqvrc(self):
        #XXX: beware the ~/.hgqvrc file
        EXPECTED = hgqvrc.DEFAULT_CONFIG.copy()
        EXPECTED["win"] = 1
        EXPECTED["bob"] = 'coin'
        EXPECTED["chandelle"] = "verte"
        EXPECTED["truc"] = 'toto'
        config = hgqvrc.read_config(input_path())
        self.assertDictEquals(config,EXPECTED)


if __name__ == '__main__':
    unittest_main()

