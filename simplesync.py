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

import gtk, simplesync_db

class dbView:
    '''Main window for viewing simplesync musicDB'''

    def __init__(self, db):
        # Initialize model
        self.db = db
        self.filtered = False

        ## Generate tooltips
        self.tooltips = gtk.Tooltips()

        ## Keyboard Accelerators
        self.AccelGroup = gtk.AccelGroup()
        self.AccelGroup.connect_group(ord('Q'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: gtk.main_quit())

        # Track view
        self.tree = gtk.TreeView()
        self.titleCol = gtk.TreeViewColumn("Title")
        self.artistCol = gtk.TreeViewColumn("Artist")
        self.albumCol = gtk.TreeViewColumn("Album")
        self.yearCol = gtk.TreeViewColumn("Year")
        self.genreCol = gtk.TreeViewColumn("Genre")
        self.syncCol = gtk.TreeViewColumn("Sync")
        col_cell_text = gtk.CellRendererText()
        for i, col in enumerate((self.titleCol, self.artistCol, self.albumCol, self.genreCol, self.yearCol)):
            col.pack_start(col_cell_text, True)
            col.add_attribute(col_cell_text, "text", i+1)
            col.set_resizable(True)
            col.set_clickable(True)
            col.set_reorderable(True)
            col.set_sort_column_id(i+1)
            col.set_property('max_width', 200)
            col.set_expand(False)
            #            col.connect('clicked', lambda w: self.column_callback(w))
            self.tree.append_column(col)
        self.titleCol.set_expand(True)
        col_cell_toggle = gtk.CellRendererToggle()
        self.syncCol.pack_start(col_cell_toggle)
        self.syncCol.set_property('max_width', 35)
        self.syncCol.add_attribute( col_cell_toggle, "active", 6)
        col_cell_toggle.set_property('activatable', True)
        col_cell_toggle.connect('toggled', self.toggle_callback)
        self.tree.append_column(self.syncCol)

        # Track window
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)

        # Search bar
        self.searchBar = gtk.Entry()
        self.searchBar.connect('activate', self.searchBar_callback)
        self.tooltips.set_tip(self.searchBar, "Enter query")
        self.searchBar.select_region(0, -1)

        # Toggle-all button
        self.toggleAllButton = gtk.Button()
        self.toggleAllButton.set_label("Toggle")
        self.toggleAllButton.connect('released', self.toggleAllButton_callback)

        # Sync-all button
        self.syncAllButton = gtk.Button()
        self.syncAllButton.set_label("All")
        self.syncAllButton.connect('released', self.syncAllButton_callback)

        # Window layout
        self.vbox1 = gtk.VBox(False, 0)
        self.hbox1 = gtk.HBox(False, 0)
        self.vbox1.pack_start(self.scroll, True, True, 1)
        self.hbox1.pack_start(self.searchBar, True, True, 1)
        self.hbox1.pack_start(self.syncAllButton, False, False, 1)
        self.hbox1.pack_start(self.toggleAllButton, False, False, 1)
        self.vbox1.pack_start(self.hbox1, False, False, 1)

        # Initialize
        self.dbwindow = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.dbwindow.set_title("simplesync")
        self.dbwindow.set_default_size(1000, 400)
        self.dbwindow.connect("destroy", lambda w: gtk.main_quit())
        self.dbwindow.add_accel_group(self.AccelGroup)
        self.dbwindow.add(self.vbox1)
        self.searchBar.grab_focus()
        self.dbwindow.show_all()

        # Populate
        # We have to make a filter here and use get_model to ref the backend so
        # we can search later on
        self.listStore = gtk.ListStore(str, str, str, str, str, int, bool)
        for track in db.allList():
            self.listStore.append([track['relpath'], track['title'], track['artist'], track['album'], track['genre'], track['year'], track['sync']])
        self.filterModel = self.listStore.filter_new()
        self.filterModel.set_visible_func(self.filterFunc, self.searchBar)
        self.tree.set_model(self.filterModel)

    def toggleAllButton_callback(self, button):
        for row in self.listStore:
            #row[6] = not row[6]
            print row[6]
        return 0

    def syncAllButton_callback(self, button):
        return

    def searchBar_callback(self, searchBar):
        '''Limit results to those containing 'searchBar'.'''
        print "Search for '%s'." % searchBar.get_text()
        self.filterModel.refilter()
        searchBar.select_region(0, -1)
        return 0

    def filterFunc(self, model, row, searchBar):
        if self.filtered: return True
        for text in model.get(row, 1, 2, 3, 4,):
            if searchBar.get_text().lower() in text.lower(): return True

    def toggle_callback(self, cell, toggle):
        '''Toggle sync status of file in db.'''
        '''Prints "0"'''
        toggle = self.filterModel.convert_path_to_child_path(toggle)
        self.listStore[toggle][6] = not self.listStore[toggle][6]
        self.db.setSync(self.listStore[toggle][0], self.listStore[toggle][6])
        print self.db.syncList()
        return

    def column_callback(self, column):
        '''Sort currently viewed tracks by column.'''
        print column.get_sort_column_id()
        print "Sort by %s." % column.get_title()
        return
    
def sync(rootDir, db):
    syncList = []
    for root, dirs, files in simplesync_db.os.walk(rootDir):
        for name in files:
            if not '.mp3' in name[-4:]:
                continue
            # Get path to file
            abspath = simplesync_db.os.path.join(root, name)
            # Encode in unicode to handle funky file names
            relpath = unicode(simplesync_db.os.path.relpath(abspath, rootDir), 'latin-1')
            if db.isNewer(rootDir, relpath):
                syncList.append(relpath)
    print syncList
            

def openDB(dbfile):
    return simplesync_db.musicDB(dbfile)

def main():
    db = openDB('/tmp/test.db')
    #db.rebuild()
    #db.addDir("/media/disk/Music/0-9")
    window = dbView(db)
    sync('/media/disk/Music/0-9', db)
    gtk.main()
    return 0

if __name__ == '__main__': main()
