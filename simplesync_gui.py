#!/usr/bin/env python
#
#       filename - desc
#       
#       Copyright 2009 John Tyree <johntyree@gmail.com>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 3 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

import pygtk, gtk

class dbView:
    '''Main gui window for viewing simplesync musicDB'''

    def __init__(self):

        ## Generate tooltips
        self.tooltips = gtk.Tooltips()

        ## Keyboard Accelerators
        self.AccelGroup = gtk.AccelGroup()
        self.AccelGroup.connect_group(ord('N'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: gtk.main_quit())

        # Track view
        self.tree = gtk.TreeView()
        self.col = gtk.TreeViewColumn("Track")
        col_cell_text = gtk.CellRendererText()
        self.col.pack_start(col_cell_text, True)
        self.col.add_attribute(col_cell_text, "text", 0)
        self.tree.append_column(self.col)
        
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)

        # Search bar
        self.searchBar = gtk.Entry()
        self.searchBar.connect('activate', self.search_callback)
        self.searchBar.select_region(0, len(self.searchBar.get_text()))
        self.tooltips.set_tip(self.searchBar, "Enter query")
        self.searchBar.set_text("Enter query")

        #Window layout
        self.vbox1 = gtk.VBox(False, 0)
        self.vbox1.pack_start(self.scroll, True, True, 1)
        self.vbox1.pack_start(self.searchBar, True, True, 1)


        #Initialize
        self.dbwindow = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.dbwindow.set_title("simplesync")
        #self.dbwindow.connect("delete_event", lambda w, e: gtk.main_quit())
        self.dbwindow.connect("destroy", lambda w: gtk.main_quit())
        self.dbwindow.add(self.vbox1)
        self.dbwindow.show_all()

    def search_callback(self, widget):
        return 0

def main():
    dbView()
    gtk.main()
    return 0

if __name__ == '__main__': main()
