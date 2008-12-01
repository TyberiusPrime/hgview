# -*- coding: iso-8859-1 -*-
#!/usr/bin/env python
# hgview.py - gtk-based hgk
#
# Copyright (C) 2007 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

"""A special renderer to draw a DAG of nodes in front of the labels"""

import gtk
import gobject
import pango
import re


class RevGraphRenderer(gtk.GenericCellRenderer):
    __gproperties__ = {
        'nodex' : ( gobject.TYPE_PYOBJECT,
                    'nodex', 'horizontal pos of node',
                    gobject.PARAM_READWRITE ),
        'edges' : ( gobject.TYPE_PYOBJECT,
                        'edges', 'list of edges',
                        gobject.PARAM_READWRITE ),
        'node' : ( gobject.TYPE_PYOBJECT,
                   'node', 'the node object',
                   gobject.PARAM_READWRITE ),
        }

    __gsignals__ = {
        'activated': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                     (gobject.TYPE_STRING, gobject.TYPE_INT))
        }
 
    def __init__(self, app):
        self.__gobject_init__()
        self.app = app
        self.r = 6

        self.nodex = 0
        self.edges = []
        self.node = None

        self.pengc = None
        self.yellowcolor = None
        self.tag_layout = None
        self.branch_layout = None
        self.text_layout = None
        self.line_pens = {}
        self.text_to_yellow = None
        self.greencolor = None
        self.colors = { }
        self.selected_node = None
        self.set_property( "mode", gtk.CELL_RENDERER_MODE_ACTIVATABLE )

    
    def set_colors( self, colors ):
        self.colors = colors
        self.colors["activated"] = "red"

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
    
    def get_branch_layout(self,widget):
        if self.branch_layout:
            return self.branch_layout
        ctx = widget.get_pango_context()
        desc = ctx.get_font_description()
        desc = desc.copy()
        desc.set_size( int(desc.get_size()*0.8) )
        self.branch_layout = pango.Layout( ctx )
        self.branch_layout.set_font_description( desc )
        return self.branch_layout

    def get_text_layout(self,widget):
        if self.text_layout:
            return self.text_layout
        ctx = widget.get_pango_context()
        self.text_layout = pango.Layout( ctx )
        return self.text_layout 

    def get_yellow_color( self, widget ):
        if self.yellowcolor:
            return self.yellowcolor
        cmap = widget.get_colormap()
        color = cmap.alloc_color("yellow")
        self.yellowcolor = color
        return color

    def get_green_color( self, widget ):
        if self.greencolor:
            return self.greencolor
        cmap = widget.get_colormap()
        color = cmap.alloc_color("green")
        self.greencolor = color
        return color 

    def get_pen_gc( self, widget, window ):
        if self.pengc:
            return self.pengc
        fgc = widget.style.fg_gc[gtk.STATE_NORMAL]
        pen = gtk.gdk.GC( window )
        pen.copy( fgc )
        self.pengc = pen
        return pen

    def get_line_pen( self, widget, window, node, width ):
        txtcolor = self.colors.get(node, "black")
        pen = self.line_pens.get(txtcolor)
        if pen is None:
            fgc = widget.style.fg_gc[gtk.STATE_NORMAL]
            pen = gtk.gdk.GC( window )
            pen.copy( fgc )
            cmap = widget.get_colormap()
            color = cmap.alloc_color(txtcolor)
            pen.set_foreground( color )
            self.line_pens[txtcolor] = pen

        pen.set_line_attributes( width, gtk.gdk.LINE_SOLID,
                                 gtk.gdk.CAP_ROUND,
                                 gtk.gdk.JOIN_BEVEL )
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

        # draw lines representing the graph
        # Hg gave us a set of tuple (node, x1, y1, x2, y2)
        # where x & y are expressed in terms of row/column numbers
        pen = self.get_pen_gc( widget, window )
        pen.set_clip_rectangle( (x,y-1,w,h+2) )
        xmax = X
        lines,n = self.edges
        active_branch = self.app.get_selected_named_branch()
        for node,x1,y1,x2,y2 in lines:
            y1-=n
            y2-=n
            if node == self.selected_node:
                node = "activated"
            # choose the right pen (line color) for the line
            hide_others = self.app.get_value_branch_checkbox()
            try:
                curr_branch = self.app.repo.read_node(node).branches['branch']
            except:
                curr_branch = None #case empty node

         
            if self.app.SHOW_GRAPH:        
                if hide_others:
                    if curr_branch == active_branch or active_branch == 'All':
                        pen = self.get_line_pen(widget, window, node, 2)
                else:
                    if curr_branch == active_branch:
                        pen = self.get_line_pen(widget, window,node, 4)
                    else:
                        pen = self.get_line_pen(widget, window,node, 2)
                           
                pen.set_clip_rectangle( (x,y-1,w,h+2) )
                window.draw_line( pen,
                              x + (2*x1+1)*W/2, y+(2*y1+1)*h/2,
                              x + (2*x2+1)*W/2, y+(2*y2+1)*h/2)
           

                # the 'and' conditions are there to handle diagonal lines properly
                if x1>xmax and (y1==0 or x1==x2):
                    xmax = x1
                if x2>xmax and (y2==0 or x1==x2):
                    xmax = x2

            # draw 2 circles (empty & filled) to display the current node
            if self.app.SHOW_GRAPH:
                window.draw_arc( bgc, True, x_ + (W-R)/2, y_+(W-R)/2, R, R, 0, 360*64 )
                window.draw_arc( fgc, False, x_ + (W-R)/2, y_+(W-R)/2, R, R, 0, 360*64 )
                
        # if required, display a nice "post-it" with tags in it
        offset = 0
        node_branches = self.app.get_node_branches()
    
        if self.node.tags and self.app.SHOW_GRAPH:
            layout = self.get_tag_layout(widget)
            layout.set_text( self.node.tags )
            w_,h_ = layout.get_size()
            d_= (h-h_/pango.SCALE)/2
            offset = w_/pango.SCALE + 3
            window.draw_layout( fgc, x + W*(xmax+1), y+d_, layout,
                                background=self.get_yellow_color(widget) )

        if self.node.rev in node_branches and self.app.SHOW_GRAPH:
            rev_from_branch = node_branches[self.node.rev]
            layout = self.get_branch_layout(widget)
            layout.set_text(rev_from_branch)
            w_,h_ = layout.get_size()
            d_= (h-h_/pango.SCALE)/2
            window.draw_layout( fgc, x + offset + W*(xmax+1), y+d_, layout,
                                background=self.get_green_color(widget) )
            offset += w_/pango.SCALE + 3
            
        layout = self.get_text_layout(widget)
        layout.set_text( self.node.short )
        searched_text = self.app.find_entry().get_text()

        #search on the string log
        from cgi import escape

        txt = escape(layout.get_text())
        try:
            str_node = unicode(txt, "utf-8")
        except UnicodeError:
            str_node = unicode(txt, "iso-8859-1", 'ignore' ) 
        
        if searched_text and searched_text in str_node :
            rexp = re.compile( '(%s)' % escape(searched_text))
            markup = rexp.sub('<span background="yellow">\\1</span>', str_node)
            layout.set_markup(markup)
        else:
            markup = str_node
            layout.set_markup('<span>%s</span>' % markup)
            
        w_,h_ = layout.get_size()
        d_ = (h-h_/pango.SCALE)/2
        window.draw_layout( fgc, x + offset + W*(xmax+2), y+d_, layout )

    def on_get_size(self, widget, cell_area):
        layout = self.get_text_layout(widget)
        try:
            txt = unicode(self.node.short, "utf-8")
        except UnicodeError:
            txt = unicode(self.node.short, "iso-8859-1", 'ignore' ) 
        layout.set_text(txt)
        tw, th = layout.get_size()
        tw /= pango.SCALE
        th /= pango.SCALE
        size = 0, 0, (self.nodex+1)*(self.r+2)+tw, max(self.r*2,th)
        return size

    def on_activate( self, event, widget, path, bg_area, cell_area, flags ):
        x, y, w, h = cell_area
        cx, cy = event.get_coords()
        m_x = cx - x
        m_y = cy - y
        fz = 1 # fuzziness allowed
        # check if a line was clicked
        h+=3 # this is needed probably because of padding
        y-=1
        W = self.r+2
        R = self.r
        X = self.nodex
        lines,n = self.edges
        for node,x1,y1,x2,y2 in lines:
            y1-=n
            y2-=n
            lx1 = (2*x1+1)*W/2 - fz
            lx2 = (2*x2+1)*W/2 + fz
            ly1 = (2*y1+1)*h/2 - fz
            ly2 = (2*y2+1)*h/2 + fz
            #print lx1,"<", m_x, "<",lx2,"&&",ly1,"<",m_y,"<",ly2 
            if lx1 <= m_x <= lx2 and ly1 <= m_y <= ly2 :
                break
                
        else: # to tell that no active part has been selected
            if self.selected_node is not None:
                widget.queue_draw()
            self.selected_node = None
            return
        if self.selected_node!=node:
            widget.queue_draw()
        self.selected_node = node

gobject.type_register( RevGraphRenderer )
