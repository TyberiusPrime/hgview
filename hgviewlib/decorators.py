# -*- coding: utf-8 -*-

import time

def timeit(f):
    """Decorator used to time the execution of a function"""
    def timefunc(*args, **kwargs):
        """wrapper"""
        t1 = time.time()
        t2 = time.clock()
        res = f(*args, **kwargs)
        t3 = time.clock()
        t4 = time.time()
        print "%s: %.2fms (time) %.2fms (clock)" % (f.func_name, 1000*(t3 - t2), 1000*(t4 - t1))
        return res
    return timefunc
