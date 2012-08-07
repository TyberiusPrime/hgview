#!/usr/bin/env python
# pylint: disable=W0142,W0403,W0404,E0611,W0613,W0622,W0622,W0704
# pylint: disable=R0904,C0103
#
# Copyright (c) 2003 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

""" Generic Setup script, takes package info from hgviewlib.__pkginfo__.py file """

from __future__ import nested_scopes, with_statement

import os
import sys
import shutil
from distutils.core import setup
from distutils.command.build import build as _build
from distutils.command.build_py import build_py as _build_py
from distutils.command.install import install as _install
from distutils.command.install_lib import install_lib
from distutils.command.install_data import install_data as _install_data
from os.path import isdir, exists, join, walk, splitext, basename
from subprocess import check_call, call as sub_call


# backport from 2.6 for 2.5

try:
    from os.path import relpath
except ImportError:
    def relpath(path, start=os.curdir):
        """Return a relative version of a path"""
        if not path:
            raise ValueError("no path specified")
        start_list = os.path.abspath(start).split(os.sep)
        path_list = os.path.abspath(path).split(os.sep)
        # Work out how much of the filepath is shared by start and path.
        i = len(os.path.commonprefix([start_list, path_list]))
        rel_list = [os.pardir] * (len(start_list) - i) + path_list[i:]
        if not rel_list:
            return os.curdir
        return join(*rel_list)


# import required features
from hgviewlib.__pkginfo__ import modname, version, license, description, \
     web, author, author_email
# import optional features
try:
    from hgviewlib.__pkginfo__ import distname
except ImportError:
    distname = modname
try:
    from hgviewlib.__pkginfo__ import scripts
except ImportError:
    scripts = []
try:
    from hgviewlib.__pkginfo__ import data_files
except ImportError:
    data_files = None
try:
    from hgviewlib.__pkginfo__ import subpackage_of
except ImportError:
    subpackage_of = None
try:
    from hgviewlib.__pkginfo__ import include_dirs
except ImportError:
    include_dirs = []
try:
    from hgviewlib.__pkginfo__ import ext_modules
except ImportError:
    ext_modules = None

long_description = file('README').read()

def setdefaultattr(obj, attrname, value=None):
    if getattr(obj, attrname, None) is not None:
        return getattr(obj, attrname)
    setattr(obj, attrname, value)
    return value

def ensure_scripts(linux_scripts):
    """
    Creates the proper script names required for each platform
    (taken from 4Suite)
    """
    from distutils import util
    if util.get_platform()[:3] == 'win':
        scripts_ = [script + '.bat' for script in linux_scripts]
    else:
        scripts_ = linux_scripts
    return scripts_


class build_qt(_build_py):

    description = "build every qt related resources (.uic and .qrc)"

    PACKAGE = 'hgviewlib.qt4'

    def dir2pkg(self, dirpath):
        os.sep.join(dispath.split('.'))

    def compile_src(self, src, dest):
        compiler = self.get_compiler(src)
        if not compiler:
            return
        dir = os.path.dirname(dest)
        self.mkpath(dir)
        sys.stderr.write("compiling %s -> %s\n" % (src, dest))
        try:
            compiler(src, dest)
        except Exception, e:
            sys.stderr.write('[Error] %r\n' % str(e))

    def run(self):
        # be sure to compile man page
        _package = self.PACKAGE.split('.')
        for dirpath, _, filenames in os.walk(self.get_package_dir(self.PACKAGE)):
            package =  dirpath.split(os.sep)
            for filename in filenames:
                module = '_'.join(filename.split(os.extsep))
                module_file = self.get_module_outfile(self.build_lib, package, module)
                src_file = os.path.join(dirpath, filename)
                self.compile_src(src_file, module_file)

    @staticmethod
    def compile_ui(ui_file, py_file):
        from PyQt4 import uic
        with open(py_file, 'w') as fp:
            uic.compileUi(ui_file, fp)

    @staticmethod
    def compile_qrc(qrc_file, py_file):
        check_call(['pyrcc4', qrc_file, '-o', py_file])

    def get_compiler(self, source_file):
        name = 'compile_' + source_file.rsplit(os.extsep, 1)[-1]
        return getattr(self, name, None)

class build_curses(_build_py):

    description = "build every qt related curses"

    def finalize_options(self):
        _build_py.finalize_options(self)
        self.packages = ['hgviewlib.curses']

class build_doc(_build):

    description = "build the documentation"

    def initialize_options (self):
        self.build_dir = None

    def finalize_options (self):
        self.set_undefined_options('build', ('build_doc', 'build_dir'))

    def run(self):
        # be sure to compile man page
        self.mkpath(self.build_dir)
        check_call(['make', '-C', self.build_dir, '-f', '../../doc/Makefile', 'VPATH=../../doc'])


class build(_build):

    user_options =  [
        ('build-doc=', None, "build directory for documentation"),
        ('no-qt', None, 'do not build qt resources'),
        ('no-curses', None, 'do not build curses resources'),
        ('no-doc', None, 'do not build the documentation'),
        ] + _build.user_options

    boolean_options = [
        'no-qt', 'no-curses', 'no-doc'
        ] + _build.boolean_options

    def initialize_options (self):
        _build.initialize_options(self)
        self.build_doc = None
        self.no_qt = False
        self.no_curses = False
        self.no_doc = False

    def finalize_options(self):
        _build.finalize_options(self)
        for attr in ('with_qt', 'with_curses', 'with_doc'):
            setdefaultattr(self.distribution, attr, True)
        if self.build_doc is None:
            self.build_doc = os.path.join(self.build_base, 'doc')
        self.distribution.with_qt &= not self.no_qt
        self.distribution.with_curses &= not self.no_curses
        self.distribution.with_doc &= not self.no_doc

    def has_qt(self):
        return self.distribution.with_qt

    def has_curses(self):
        return self.distribution.with_curses

    def has_doc(self):
        return self.distribution.with_doc

    # 'sub_commands': a list of commands this command might have to run to
    # get its work done.  See cmd.py for more info.
    sub_commands = [
        ('build_qt', has_qt),
        ('build_curses', has_curses),
        ('build_doc', has_doc),
        ] + _build.sub_commands


class install_qt(install_lib):

    description = "install the qt interface resources"

    def run(self):
        if not self.skip_build:
            self.run_command('build_qt')
        self.distribution.packages.append('hgviewlib.qt4')
        install_lib.run(self)


class install_curses(install_lib):

    description = "install the curses interface resources"

    def run(self):
        self.distribution.packages.append('hgviewlib.curses')
        install_lib.run(self)


class install_doc(_install_data):

    description = "install the documentation"

    def initialize_options (self):
        _install_data.initialize_options(self)
        self.install_dir = None
        self.build_dir = None

    def finalize_options (self):
        _install_data.finalize_options(self)
        self.set_undefined_options('build', ('build_doc', 'build_dir'))
        self.set_undefined_options('install', ('install_base', 'install_dir'))

    def run(self):
        check_call(['make', '-C', self.build_dir, '-f',
                    '../../doc/Makefile',
                    'VPATH=../../doc',
                    'install',
                    'PREFIX=%s' % self.install_dir])


class install(_install):
    user_options = [
            ('no-qt', None, "do not install qt library part"),
            ('no-curses', None, "do not install curses library part"),
            ('no-doc', None, "do not install the documentation"),
            ] + _install.user_options

    boolean_options = [
            'no-qt', 'no-curses', 'no-doc'
            ] + _install.boolean_options

    def initialize_options(self):
        self.install_doc = None
        self.no_qt = False
        self.no_curses = False
        self.no_doc = False
        _install.initialize_options(self)

    def finalize_options(self):
        _install.finalize_options(self)
        for attr in ('with_qt', 'with_curses', 'with_doc'):
            setdefaultattr(self.distribution, attr, True)
        self.distribution.with_qt &= not self.no_qt
        self.distribution.with_curses &= not self.no_curses
        self.distribution.with_doc &= not self.no_doc

    def has_qt(self):
        return self.distribution.with_qt

    def has_curses(self):
        return self.distribution.with_curses

    def has_doc(self):
        return self.distribution.with_doc

    # 'sub_commands': a list of commands this command might have to run to
    # get its work done.  See cmd.py for more info.
    sub_commands = [
        ('install_qt', has_qt),
        ('install_curses', has_curses),
        ('install_doc', has_doc),
        ] + _install.sub_commands


def main():
    """setup entry point"""
    kwargs = {}
    # to generate qct MSI installer, you run python setup.py bdist_msi
    #from setuptools import setup
    if os.name in ['nt']:
        # the msi will automatically install the qct.py plugin into hgext
        kwargs['data_files'] = [('lib/site-packages/hgext', ['hgext/hgview.py']),
                ('mercurial/hgview.d', ['hgview.rc']),
                ('share/hgview', ['README'])]
        scripts = ['win32/hgview_postinstall.py']
    else:
        scripts = ['bin/hgview']

    kwargs['package_dir'] = {modname : modname}
    packages = ['hgviewlib', 'hgext', 'hgviewlib.hgpatches']
    kwargs['packages'] = packages
    return setup(name=distname,
                 version=version,
                 license=license,
                 description=description,
                 long_description=long_description,
                 author=author,
                 author_email=author_email,
                 url=web,
                 scripts=ensure_scripts(scripts),
                 data_files=data_files,
                 ext_modules=ext_modules,
                 cmdclass={'build_qt': build_qt,
                           'build_curses': build_curses,
                           'build_doc': build_doc,
                           'build' : build,
                           'install_qt': install_qt,
                           'install_curses': install_curses,
                           'install_doc': install_doc,
                           'install':install,
                           },
                 **kwargs
                 )

if __name__ == '__main__' :
    main()
