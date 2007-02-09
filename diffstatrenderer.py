"""A special renderer to draw a diffstat bar in a treeview column"""

import gtk
import gobject
import pango

class DiffStatRenderer(gtk.GenericCellRenderer):
    __gproperties__ = {
        'stats' : ( gobject.TYPE_PYOBJECT,
                    'stats', 'a triplet (add,sub,total)',
                    gobject.PARAM_READWRITE ),
        }

    def __init__(self):
        self.__gobject_init__()
        self.stats = None
        self.pengc = None
        self.redgc = None
        self.greengc = None
        self.colors = {}

    def do_get_property( self, propname ):
        return getattr( self, propname.name )

    def do_set_property( self, propname, value):
        setattr(self, propname.name, value)

    def get_color( self, widget, color_name ):
        if color_name not in self.colors:
            cmap = widget.get_colormap()
            color = cmap.alloc_color(color_name)
            self.colors[color_name] = color
            return color
        else:
            return self.colors[color_name]

    def make_pen( self, widget, window, fg=None, bg=None, line=None ):
        """helper function to create a pen specifying its
        fg, bg colors
        line attributes (w, style, cap, join) ex:
           line=(2,gtk.gdk.LINE_SOLID,gtk.gdk.CAP_ROUND,gtk.gdk.JOIN_BEVEL)
        """
        fgc = widget.style.fg_gc[gtk.STATE_NORMAL]
        pen = gtk.gdk.GC( window )
        pen.copy( fgc )
        if fg:
            color = self.get_color( widget, fg )
            pen.set_foreground( color )
        if bg:
            color = self.get_color( widget, bg )
            pen.set_background( color )
        if line:
            pen.set_line_attributes( *line )
        return pen

    def get_pen_gc( self, widget, window ):
        if not self.pengc:
            self.pengc = self.make_pen( widget, window )
        return self.pengc
    def get_green_pen( self, widget, window ):
        if not self.greengc:
            self.greengc = self.make_pen( widget, window, fg="darkgreen" )
        return self.greengc
    def get_red_pen( self, widget, window ):
        if not self.redgc:
            self.redgc = self.make_pen( widget, window, fg="darkred" )
        return self.redgc
    def get_bg_pen( self, widget, window ):
        if not self.bgpen:
            self.bgpen = self.make_pen( widget, window, fg='grey' )
        return self.bgpen

    def on_render(self, window, widget, background_area,
                  cell_area, expose_area, flags ):
        if self.stats is None:
            return
        if self.stats[2]==0:
            return
        x, y, w, h = cell_area
        h2 = (h*80)/100
        y = y + (h-h2)/2
        h = h2
        fgc = widget.style.fg_gc[gtk.STATE_NORMAL]
        bgc = widget.style.bg_gc[gtk.STATE_NORMAL]

        wg = (w*self.stats[0])/self.stats[2]
        wr = (w*self.stats[1])/self.stats[2]
        window.draw_rectangle( bgc, True, x, y, w, h )
        pen = self.get_green_pen( widget, window )
        window.draw_rectangle( pen, True, x, y, wg, h )
        pen = self.get_red_pen( widget, window )
        window.draw_rectangle( pen, True, x+wg, y, wr, h )
        window.draw_rectangle( fgc, False, x, y, w, h )

    def on_get_size(self, widget, cell_area):
        return 0, 0, 50, 10

gobject.type_register( DiffStatRenderer )
