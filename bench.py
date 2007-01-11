
from time import time

from mercurial import hg, ui

def tolocal(s):
    return s
import mercurial.util
mercurial.util.tolocal = tolocal

repo = hg.repository( ui.ui() )

ch = repo.changelog
n=ch.count()

def build_nodes():
    t1=time();
    nodes = [ ch.node(i) for i in xrange(n) ]
    t2=time()
    print "Retrieving nodes", t2-t1
    return nodes

def build_info(nodes):
    info = {}
    t1=time();
    for n in nodes:
        t = ch.read( n )
        info[n] = t
    t2=time()
    print "Reading nodes info", t2-t1
    return info

import hotshot

prof = hotshot.Profile("/home/ludal/hg2.prof")

nodes = build_nodes()
#prof.run("info = build_info(nodes)")
info = build_info(nodes)

## import sys
## sys.exit(0)

## info = {}
## t1=time();
## for n in nodes:
##     t = ch.read( n )
##     info[n] = t
## t2=time()
## print "Reading nodes info 2", t2-t1

uid=0
authors = {}
fileset = {}
s_id = s_authors=s_date=s_filelist=s_log = 0
t1=time()
for k,v in info.items():
    id,author,date,filelist,log,unk = v
    s_id+=4
    s_authors+=len(author)
    s_date+=len(date)
    s_filelist+=sum( len(f) for f in filelist )
    s_log += len(log)
    if author not in authors:
        authors[author] = uid
        uid+=1
    for f in filelist:
        if f not in fileset:
            fileset[f] = uid
            uid+=1
t2=time()
print "Computing sizes", t2-t1
print "COUNT=", len(info)
print "ID=", s_id/1000000.
print "AUTH=", s_authors/1000000.
print "DATE=", s_date/1000000.
print "FILES=", s_filelist/1000000.
print "LOG=", s_log/1000000.
print "Unique authors", len(authors)
print "Unique files", len(fileset)

print "Saved by indexing filenames", (s_filelist-s_id-sum( 4+len(f) for f in fileset.keys() )) / 1000000.
print "Saved by indexing authors", (s_authors-s_id-sum( 4+len(f) for f in authors.keys() )) / 1000000.

# linx-2.6-hg
# test rev 17 :
#ludal     6466 76.9 52.7 489040 477976 pts/2   S+   22:18   2:13 python /home/ludal/SB/public/hgview/hgview.py
# rev 18
#ludal     7102 60.0 46.3 430656 420192 pts/6   S+   01:19   2:11 python /home/ludal/SB/public/hgview/hgview.py
# rev 19
#ludal     7265 70.0 31.7 297008 288012 pts/6   S+   02:34   1:10 python /home/ludal/SB/public/hgview/hgview.py

# ginco
# rev 17
# ludal     6491 14.1  1.7  23200 16236 pts/0    S+   22:22   0:04 python /home/ludal/SB/public/hgview/hgview.py
# rev 18
# ludal     6626  5.8  1.8  23760 16668 pts/0    S+   23:13   0:02 python /home/ludal/SB/public/hgview/hgview.py
