
import gtk
import gobject
import pango

class RevGraphRenderer(gtk.GenericCellRenderer):
    __gproperties__ = {
        'nodex' : ( gobject.TYPE_PYOBJECT,
                    'nodex', 'horizontal pos of node',
                    gobject.PARAM_READWRITE ),
        'edges' : ( gobject.TYPE_PYOBJECT,
                        'edges', 'list of edges',
                        gobject.PARAM_READWRITE ),
        'text' : ( gobject.TYPE_STRING,
                   'edges', 'list of edges', "",
                   gobject.PARAM_READWRITE ),
        }


    def __init__(self):
        self.__gobject_init__()
        self.r = 10
        self.nodex = 0
        self.edges = []
        self.pen = None
        
    def do_get_property( self, propname ):
        return getattr( self, propname.name )

    def do_set_property( self, propname, value):
        setattr(self, propname.name, value)

    def on_render(self, window, widget, background_area,
                  cell_area, expose_area, flags ):
        x, y, w, h = cell_area
        h+=3 # this is probably padding
        y-=1
        W = h
        R = self.r
        X = self.nodex
        fgc = widget.style.fg_gc[gtk.STATE_NORMAL]
        bgc = widget.style.bg_gc[gtk.STATE_NORMAL]
        x_ = x + W*X
        y_ = y + (h-W)/2

        #xc = x + W/2
        #yc = y + h/2
        if not self.pen:
            pen = gtk.gdk.GC( window )
            pen.copy( fgc )
            self.pen = pen
        else:
            pen = self.pen
        pen.set_clip_rectangle( (x,y-1,w,h+2) )
        xmax = X
        for x1,y1,x2,y2 in self.edges:
            window.draw_line( pen,
                              x + (2*x1+1)*W/2, y+(2*y1+1)*h/2,
                              x + (2*x2+1)*W/2, y+(2*y2+1)*h/2 )
            if x1>xmax and (y1==0 or x1==x2):
                xmax = x1
            if x2>xmax and (y2==0 or x1==x2):
                xmax = x2


        window.draw_arc( bgc, True, x_ + (W-R)/2, y_+(W-R)/2, R, R, 0, 360*64 )
        window.draw_arc( fgc, False, x_ + (W-R)/2, y_+(W-R)/2, R, R, 0, 360*64 )

        ctx = widget.get_pango_context()
        layout = pango.Layout( ctx )
        layout.set_text( self.text )
        w_,h_ = layout.get_size()
        d_ = (h-h_/pango.SCALE)/2
        window.draw_layout( fgc, x + W*(xmax+1), y+d_, layout )

    def on_get_size(self, widget, cell_area):
        ctx = widget.get_pango_context()
        layout = pango.Layout( ctx )
        layout.set_text( self.text )
        tw, th = layout.get_size()
        tw /= pango.SCALE
        th /= pango.SCALE
        size = 0, 0, (self.nodex+1)*self.r*2+tw, max(self.r*2,th)
        return size


gobject.type_register( RevGraphRenderer )
