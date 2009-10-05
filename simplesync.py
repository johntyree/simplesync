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

import gtk, simplesync_db, time, os, shutil

class dbView:
    '''Main window for viewing simplesync musicDB'''

    def __init__(self, dbFile = None):
        self.dbFile = dbFile

        # Initialize model
        self.allToggle = None
        self.filtered = None

        ## Generate tooltips
        self.tooltips = gtk.Tooltips()

        ## Keyboard Accelerators
        self.AccelGroup = gtk.AccelGroup()
        self.AccelGroup.connect_group(ord('Q'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: gtk.main_quit())
        self.AccelGroup.connect_group(ord('P'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: self.editPrefs())

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
            col.connect("clicked", self.rearrange, i+1)
            #col.set_sort_column_id(i+1)
            col.set_property('max_width', 200)
            col.set_expand(False)
            #            col.connect('clicked', lambda w: self.column_callback(w))
            self.tree.append_column(col)
        self.titleCol.set_expand(True)
        col_cell_toggle = gtk.CellRendererToggle()
        self.syncCol.pack_start(col_cell_toggle)
        self.syncCol.set_clickable(True)
        self.syncCol.set_property('max_width', 35)
        self.syncCol.connect("clicked", self.rearrange, i+1)
        self.syncCol.add_attribute(col_cell_toggle, "active", 6)
        col_cell_toggle.set_property('activatable', True)
        col_cell_toggle.connect('toggled', self.toggle_callback)
        self.tree.append_column(self.syncCol)
        self.tree.set_rules_hint(True)

        # Track window
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)

        # Search bar
        self.searchBar = gtk.Entry()
        self.searchBar.connect('changed', self.searchBar_callback)
        self.tooltips.set_tip(self.searchBar, "Enter query")

        # Toggle-all button
        self.toggleAllButton = gtk.Button()
        self.toggleAllButton.set_label("_Toggle")
        self.toggleAllButton.connect('clicked', self.toggleAllButton_callback)
        self.tooltips.set_tip(self.toggleAllButton, "Toggle sync of all files")

        # Set all button
        self.setAllButton = gtk.Button()
        self.setAllButton.set_label("Set _all")
        self.setAllButton.connect('clicked', self.setAllButton_callback)
        self.tooltips.set_tip(self.setAllButton, "Enable or disable sync of all files")

        # Sync button
        self.syncAllButton = gtk.Button('_Sync')
        self.syncAllButton.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_BUTTON))
        self.syncAllButton.connect('clicked', self.syncAllButton_callback)
        self.tooltips.set_tip(self.syncAllButton, "Sync active files to device")

        # Window layout
        self.vbox1 = gtk.VBox(False, 0)
        self.hbox1 = gtk.HBox(False, 0)
        self.vbox1.pack_start(self.scroll, True, True, 1)
        self.hbox1.pack_start(self.searchBar, True, True, 1)
        self.hbox1.pack_start(self.setAllButton, False, False, 1)
        self.hbox1.pack_start(self.toggleAllButton, False, False, 1)
        self.hbox1.pack_start(self.syncAllButton, False, False, 1)
        self.vbox1.pack_start(self.hbox1, False, False, 1)

        # Initialize
        self.dbwindow = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.dbwindow.set_title("SimpleSync")
        self.dbwindow.set_default_size(1000, 400)
        self.dbwindow.connect("destroy", lambda w: gtk.main_quit())
        self.dbwindow.add_accel_group(self.AccelGroup)
        self.dbwindow.add(self.vbox1)
        self.searchBar.grab_focus()
        self.dbwindow.show_all()

        # Populate
        try:
            self.view(self.dbFile)
        except NameError:
            pass

    def rearrange(self, col, n):
        if col.get_sort_order() == gtk.SORT_ASCENDING:
            col.set_sort_order(gtk.SORT_DESCENDING)
        else:
            col.set_sort_order(gtk.SORT_ASCENDING)
        self.listStore.set_sort_column_id(n, col.get_sort_order())
        col.set_sort_indicator(True)

    def view(self, dbFile):
        '''Load the database into the dbView.'''
        # We have to make a filter here and use get_model to ref the backend so
        # we can search later on
        if dbFile == None:
            print "No file specified!"
            return
        db = self.openDB(dbFile)
        self.db = db
        self.dbwindow.set_title('SimpleSync - %s: [ %s -> %s ]' % (dbFile, self.db.sourceDir(), self.db.targetDir()))
        self.listStore = gtk.ListStore(str, str, str, str, str, int, bool)
        for track in db.allList():
            self.listStore.append([track['relpath'], track['title'], track['artist'], track['album'], track['genre'], track['year'], track['sync']])
        self.filterModel = self.listStore.filter_new()
        self.filterModel.set_visible_func(self.filterFunc, self.searchBar)
        self.tree.set_model(self.filterModel)
        self.updateTitle()

    def updateTitle(self):
        '''Update window title.'''
        syncSize = self.db.syncSize() / 1024.**2
        if syncSize > 1024:
            syncSize /= 1024.0
            syncSize = '%.2f Gib' % syncSize
        else:
            syncSize = '%.2f Mib' % syncSize

        if len(self.filterModel):
            self.dbwindow.set_title('SimpleSync - %s: [ %s -> %s ] (%i/%i) (%s)' % (self.dbFile, self.db.sourceDir(), self.db.targetDir(), len(self.filterModel), len(self.listStore), syncSize))
        else:
            self.dbwindow.set_title('SimpleSync - %s: [ %s -> %s ] (%i) (%s)' % (self.dbFile, self.db.sourceDir(), self.db.targetDir(), len(self.listStore), syncSize()))
        

    def searchBar_callback(self, searchBar):
        '''Limit results to those containing 'searchBar'.'''
        self.filterModel.refilter()

    def filterFunc(self, model, row, searchBar):
        '''Return True if searchBarText matches any part of any column in row.'''
        if self.filtered: return True
        searchBarText = searchBar.get_text().lower()
        for text in model.get(row, 1, 2, 3, 4,):
            if searchBarText in text.lower(): return True

    def toggle_callback(self, cell, toggleList):
        '''Toggle sync status of a tuple of files in db.'''
        # Ugly workaround based on coincidence... toggleList must be an iteratable!
        if cell != None:
            toggleList = (toggleList,)
        print toggleList[0]
        fileList = []
        # Build list of files to set.
        for toggle in toggleList:
            toggle = self.filterModel.convert_path_to_child_path(toggle)
            self.listStore[toggle][6] = not self.listStore[toggle][6]
            fileList.append((self.listStore[toggle][0], self.listStore[toggle][6]))
        self.db.setSync(fileList)
        return

    def column_callback(self, column):
        '''Sort currently viewed tracks by column'''
        print column.get_sort_column_id()
        print "Sort by %s." % column.get_title()
        return

    def toggleAllButton_callback(self, button):
        '''Toggle sync status of all visible files'''
        fileList = []
        # Build list of files to toggle.
        for i, row in enumerate(self.filterModel):
            fileList.append(i)
        # Toggle them all at once
        self.toggle_callback(None, fileList)
        return

    def setAllButton_callback(self, button):
        '''Set or unset sync status of all visible files'''
        fileList = []
        self.allToggle = not self.allToggle
        for i, row in enumerate(self.filterModel):
            childPath = self.filterModel.convert_path_to_child_path(i)
            self.listStore[childPath][6] = self.allToggle
            fileList.append((self.listStore[childPath][0], self.allToggle))
        self.db.setSync(fileList)
        return

    def syncAllButton_callback(self, button):
        '''Copy marked files from self.targetDir to self.sourceDir'''
        sourceDir = self.db.sourceDir()
        targetDir = self.db.targetDir()
        # If we're missing some info, get it!
        while (not sourceDir or not targetDir) and self.errorDialog('Specify a source and target') and self.editPrefs() == gtk.RESPONSE_OK:
            sourceDir = self.db.sourceDir()
            targetDir = self.db.targetDir()
        print "Sync: %s -> %s" % (sourceDir, targetDir)
        for file in self.db.copyList(sourceDir):
            abspath = os.path.join(sourceDir, file).encode('latin-1')
            target = os.path.join(targetDir,file).encode('latin-1')
            print abspath, '->', target
            if not os.path.isdir(os.path.dirname(target)):
                os.makedirs(os.path.dirname(target))
            shutil.copy2(abspath, target)
            self.db.updateFile(sourceDir, abspath)
        self.db.connection.commit()
        self.db.mtime(time.time())

    def editPrefs(self):
        d = dbPrefsdialog()
        if d.response == gtk.RESPONSE_OK or d.response == gtk.RESPONSE_APPLY:
            dbFile = d.get_Path('DB File')
            if dbFile:
                self.dbFile = dbFile
                self.view(dbFile)
            source = d.get_Path('Source')
            if os.path.isdir(source):
                self.db.sourceDir(source)
                if d.response == gtk.RESPONSE_APPLY:
                    self.db.recurseDir(source, self.db.updateFile)
            target = d.get_Path('Target')
            if target != '':
                self.db.targetDir(target)
        return d.response

    def openDB(self, dbFile):
        '''Returns a musicDB object connected to dbFile.'''
        return simplesync_db.musicDB(dbFile)

    def errorDialog(self, msg = "Error!"):
        md = gtk.MessageDialog(,
                               gtk.DIALOG_DESTROY_WITH_PARENT,
                               gtk.MESSAGE_ERROR, 
                               gtk.BUTTONS_CLOSE,
                               msg)
        md.run()
        md.destroy()
        return True


class dbPrefsdialog(gtk.Window):
    '''Dialog box for setting file paths.'''
    def __init__(self):
        self.dialog = gtk.Dialog("File Prefs", self, 0, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                                         gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.dialog.add_button(gtk.STOCK_SAVE_AS, gtk.RESPONSE_APPLY).set_label('Import')
        vbox = gtk.VBox(False, 8)
        vbox.set_border_width(8)
        self.fileEntryGroups = {}
        self.fileEntrySizeGroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        # Creating the labels, entry boxes, buttons
        for i, name in enumerate(('DB File', 'Source', 'Target')):
            self.insertEntryGroup(vbox, name, self.fileEntryGroups, i in (1, 2))

        self.dialog.vbox.pack_start(vbox, False, False, 0)
        self.dialog.show_all()
        self.response = self.dialog.run()
        self.dialog.destroy()

    def insertEntryGroup(self, box, name, dict, isFolder = False):
        # Folder is selected if isFolder == True
        sizeGroup = self.fileEntrySizeGroup
        widget = gtk.Entry()
        dict[name] = widget
        label = gtk.Label(name + ':')
        label.set_alignment(1, 0.5)
        label.set_mnemonic_widget(widget)
        sizeGroup.add_widget(label)
        button = gtk.Button(name, gtk.STOCK_OPEN)
        button.connect('clicked', lambda x: self.on_browse_button_clicked(widget, isFolder))
        hbox = gtk.HBox(False, 8)
        for i in (label, widget, button):
            hbox.pack_start(i, False, False, 1)
        box.pack_start(hbox, False, False, 0)

    def on_browse_button_clicked(self, entry, isFolder = False):
        file = self.selectFile(isFolder)
        if file:
            entry.set_text(file)

    def get_Path(self, name):
        return self.fileEntryGroups[name].get_text()

    def selectFile(self, isFolder):
        '''Return selected file.'''
        if isFolder:
            isFolder = gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER
        else:
            isFolder = gtk.FILE_CHOOSER_ACTION_OPEN
        dialog = gtk.FileChooserDialog("Select...",
                                       None,
                                       isFolder,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_select_multiple(False)
        response = dialog.run()
        try:
            if response == gtk.RESPONSE_OK:
                return dialog.get_filename()
            elif response == gtk.RESPONSE_CANCEL:
                return
        finally:
            dialog.destroy()

def main():
    #print db.allList()
    window = dbView('/tmp/ss2.db')
    #window.db.recurseDir("/media/disk/Music/0-9", window.db.updateFile)
    #window.view('/tmp/ss2.db')
    #window.view('/tmp/simplesync.db')
    gtk.main()
    return 0

if __name__ == '__main__': main()
