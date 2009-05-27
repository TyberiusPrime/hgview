import re
from PyQt4 import QtCore, QtGui, Qsci, uic

class _LexerSelector(object):
    lexer = None
    def match(self, filename, filedata):
        return False

class _FilenameLexerSelector(object):
    extensions = ()
    def match(self, filename, filedata):
        filename = filename.lower()
        for ext in self.extensions:
            if filename.endswith(ext):
                return True
        return False

class _ScriptLexerSelector(_FilenameLexerSelector):
    regex = None
    headersize = 3
    def match(self, filename, filedata):
        if super(_ScriptLexerSelector, self).match(filename, filedata):
            return True
        if self.regex:
            for line in filedata.splitlines()[:self.headersize]:
                if len(line)<1000 and self.regex.match(line):
                    return True
        return False
        
class PythonLexerSelector(_ScriptLexerSelector):
    extensions = ('.py', '.pyw')    
    lexer = Qsci.QsciLexerPython
    regex = re.compile(r'^#[!].*python')

class BashLexerSelector(_ScriptLexerSelector):
    extensions = ('.sh', '.bash')
    lexer = Qsci.QsciLexerBash
    regex = re.compile(r'^#[!].*sh')

class PerlLexerSelector(_ScriptLexerSelector):
    extensions = ('.pl', '.perl')
    lexer = Qsci.QsciLexerPerl
    regex = re.compile(r'^#[!].*perl')

class RubyLexerSelector(_ScriptLexerSelector):
    extensions = ('.rb', '.ruby')
    lexer = Qsci.QsciLexerRuby
    regex = re.compile(r'^#[!].*ruby')

class LuaLexerSelector(_ScriptLexerSelector):
    extensions = ('.lua', )
    lexer = Qsci.QsciLexerLua
    regex = None

class CppLexerSelector(_FilenameLexerSelector):
    extensions = ('.c', '.cpp', '.cxx', '.h', '.hpp', '.hxx')
    lexer = Qsci.QsciLexerCPP

class CSSLexerSelector(_FilenameLexerSelector):
    extensions = ('.css',)
    lexer = Qsci.QsciLexerCSS

class HTMLLexerSelector(_FilenameLexerSelector):
    extensions = ('.htm', '.html', '.xhtml', '.xml')
    lexer = Qsci.QsciLexerHTML

class MakeLexerSelector(_FilenameLexerSelector):
    extensions = ('.mk', 'makefile')
    lexer = Qsci.QsciLexerMakefile

class SQLLexerSelector(_FilenameLexerSelector):
    extensions = ('.sql',)
    lexer = Qsci.QsciLexerSQL

class JSLexerSelector(_FilenameLexerSelector):
    extensions = ('.js',)
    lexer = Qsci.QsciLexerJavaScript

class JavaLexerSelector(_FilenameLexerSelector):
    extensions = ('.java',)
    lexer = Qsci.QsciLexerJava

class TeXLexerSelector(_FilenameLexerSelector):
    extensions = ('.tex', '.latex',)
    lexer = Qsci.QsciLexerTeX

    
lexers = [cls() for clsname, cls in globals().items() if not clsname.startswith('_') and isinstance(cls, type) and \
          issubclass(cls, (_LexerSelector, _FilenameLexerSelector, _ScriptLexerSelector))]

def get_lexer(filename, filedata, fileflag=None):
    if fileflag == "=":
        return Qsci.QsciLexerDiff
    for lselector in lexers:
        if lselector.match(filename, filedata):
            return lselector.lexer()
    return None

        
