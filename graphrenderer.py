
import gtk
import gobject

class RevGraphRenderer(gtk.GenericCellRenderer):
    __gproperties__ = {
        'nodex' : ( gobject.TYPE_PYOBJECT,
                    'nodex', 'horizontal pos of node',
                    gobject.PARAM_READWRITE ),
        'edges' : ( gobject.TYPE_PYOBJECT,
                        'edges', 'list of edges',
                        gobject.PARAM_READWRITE ),
        }


    def __init__(self):
        self.__gobject_init__()
        self.w = 10
        self.nodex = 0
        self.edges = []
        
    def do_get_property( self, propname ):
        return getattr( self, propname.name )

    def do_set_property( self, propname, value):
        setattr(self, propname.name, value)

    def on_render(self, window, widget, background_area,
                  cell_area, expose_area, flags ):
        x, y, w, h = cell_area
        print x,y,w,h
        h+=3
        y-=1
        W = self.w
        X = self.nodex
        fgc = widget.style.fg_gc[gtk.STATE_NORMAL]
        x_ = x + W*X
        y_ = y + (h-W)/2
        window.draw_arc( fgc, False, x_, y_, W, W, 0, 360*64 )

        #xc = x + W/2
        #yc = y + h/2
        for x1,y1,x2,y2 in self.edges:
            window.draw_line( fgc,
                              x + (2*x1+1)*W/2, y+(2*y1+1)*h/2,
                              x + (2*x2+1)*W/2, y+(2*y2+1)*h/2 )


    def on_get_size(self, widget, cell_area):
        return 0, 0, (self.nodex+1)*self.w, self.w


gobject.type_register( RevGraphRenderer )
