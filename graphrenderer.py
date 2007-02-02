
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
        'text' : ( gobject.TYPE_PYOBJECT,
                   'edges', 'list of edges',
                   gobject.PARAM_READWRITE ),
        'tags' : ( gobject.TYPE_STRING,
                   'tags', 'tags to display', "",
                   gobject.PARAM_READWRITE ),
        }


    def __init__(self):
        self.__gobject_init__()
        self.r = 6
        self.nodex = 0
        self.edges = []
        self.text = ""
        self.tags = ""
        self.pengc = None
        self.yellowcolor = None
        self.tag_layout = None
        self.text_layout = None
        self.line_pens = {}
        self.colors = {}

    def do_get_property( self, propname ):
        return getattr( self, propname.name )

    def do_set_property( self, propname, value):
        setattr(self, propname.name, value)

    def get_tag_layout(self,widget):
        if self.tag_layout:
            return self.tag_layout
        ctx = widget.get_pango_context()
        desc = ctx.get_font_description()
        desc = desc.copy()
        desc.set_size( int(desc.get_size()*0.8) )
        self.tag_layout = pango.Layout( ctx )
        self.tag_layout.set_font_description( desc )
        return self.tag_layout

    def get_text_layout(self,widget):
        if self.text_layout:
            return self.text_layout
        ctx = widget.get_pango_context()
        self.text_layout = pango.Layout( ctx )
        return self.text_layout

    def get_yellow_color( self, widget ):
        if not self.yellowcolor:
            cmap = widget.get_colormap()
            color = cmap.alloc_color("yellow")
            self.yellowcolor = color
            return color
        else:
            return self.yellowcolor

    def get_pen_gc( self, widget, window ):
        if not self.pengc:
            fgc = widget.style.fg_gc[gtk.STATE_NORMAL]
            pen = gtk.gdk.GC( window )
            pen.copy( fgc )
            self.pengc = pen
            return pen
        else:
            return self.pengc

    def get_line_pen( self, widget, window, node ):
        txtcolor = self.colors.get(node,"black")
        pen = self.line_pens.get(txtcolor)
        if pen is None:
            fgc = widget.style.fg_gc[gtk.STATE_NORMAL]
            pen = gtk.gdk.GC( window )
            pen.copy( fgc )
            cmap = widget.get_colormap()
            color = cmap.alloc_color(txtcolor)
            pen.set_foreground( color )
            self.line_pens[txtcolor] = pen
        return pen

    def on_render(self, window, widget, background_area,
                  cell_area, expose_area, flags ):
        x, y, w, h = cell_area
        h+=3 # this is needed probably because of padding
        y-=1
        W = self.r+2
        R = self.r
        X = self.nodex
        fgc = widget.style.fg_gc[gtk.STATE_NORMAL]
        bgc = widget.style.bg_gc[gtk.STATE_NORMAL]
        x_ = x + W*X
        y_ = y + (h-W)/2

        pen = self.get_pen_gc( widget, window )
        pen.set_clip_rectangle( (x,y-1,w,h+2) )
        xmax = X
        lines,n = self.edges
        for node,x1,y1,x2,y2 in lines:
            y1-=n
            y2-=n
            pen = self.get_line_pen(widget,window,node)
            window.draw_line( pen,
                              x + (2*x1+1)*W/2, y+(2*y1+1)*h/2,
                              x + (2*x2+1)*W/2, y+(2*y2+1)*h/2 )
            # the 'and' conditions are there to handle diagonal lines properly
            if x1>xmax and (y1==0 or x1==x2):
                xmax = x1
            if x2>xmax and (y2==0 or x1==x2):
                xmax = x2


        window.draw_arc( bgc, True, x_ + (W-R)/2, y_+(W-R)/2, R, R, 0, 360*64 )
        window.draw_arc( fgc, False, x_ + (W-R)/2, y_+(W-R)/2, R, R, 0, 360*64 )

        offset = 0
        if self.tags:
            layout = self.get_tag_layout(widget)
            layout.set_text( self.tags )
            w_,h_ = layout.get_size()
            d_= (h-h_/pango.SCALE)/2
            offset = w_/pango.SCALE + 3
            window.draw_layout( fgc, x + W*(xmax+1), y+d_, layout,
                                background=self.get_yellow_color(widget) )

        layout = self.get_text_layout(widget)
        layout.set_text( self.text )
        w_,h_ = layout.get_size()
        d_ = (h-h_/pango.SCALE)/2
        window.draw_layout( fgc, x + offset + W*(xmax+2), y+d_, layout )

    def on_get_size(self, widget, cell_area):
        layout = self.get_text_layout(widget)
        layout.set_text( self.text )
        tw, th = layout.get_size()
        tw /= pango.SCALE
        th /= pango.SCALE
        size = 0, 0, (self.nodex+1)*(self.r+2)+tw, max(self.r*2,th)
        return size


gobject.type_register( RevGraphRenderer )
