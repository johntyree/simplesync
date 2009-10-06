#!/usr/bin/env python
#
#       simplesync.py
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

import gtk, simplesync_db, time, os, shutil, sys

class dbView:
    '''Main window for viewing simplesync musicDB'''

    def __init__(self, dbFile = None):
        self.echo = False
        self.appPath = os.path.abspath(os.path.dirname(os.path.realpath(sys.argv[0])))
        self.dbFile = dbFile

        # Initialize model
        self.allToggle = None
        self.filtered = None

        ## Generate tooltips
        self.tooltips = gtk.Tooltips()

        ## Keyboard Accelerators
        self.AccelGroup = gtk.AccelGroup()
        self.AccelGroup.connect_group(ord('P'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: self.editPrefs())
        self.AccelGroup.connect_group(ord('Q'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: gtk.main_quit())
        self.AccelGroup.connect_group(ord('S'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: self.toggleSelectedButton_callback(x))

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
        self.tree.connect("row-activated", self.row_callback)
        self.tree.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        # Track window
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)

        # Search bar
        self.searchBar = gtk.Entry()
        self.searchBar.connect('changed', self.searchBar_callback)
        self.tooltips.set_tip(self.searchBar, "Enter query.")

        # Toggle Selected button
        self.toggleSelectedButton = gtk.Button()
        self.toggleSelectedButton.set_label("_Toggle")
        self.toggleSelectedButton.connect('clicked', self.toggleSelectedButton_callback)
        self.tooltips.set_tip(self.toggleSelectedButton, "Toggle sync of all files.")

        # Delete Selected button
        self.deleteSelectedButton = gtk.Button()
        self.deleteSelectedButton.set_label("_Delete")
        self.deleteSelectedButton.connect('clicked', self.deleteSelectedButton_callback)
        self.tooltips.set_tip(self.deleteSelectedButton, "Delete all selected files.")

        # Sync button
        self.syncAllButton = gtk.Button('_Sync')
        self.syncAllButton.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_BUTTON))
        self.syncAllButton.connect('clicked', self.syncAllButton_callback)
        self.tooltips.set_tip(self.syncAllButton, "Sync active files to device.")

        # Window layout
        self.vbox1 = gtk.VBox(False, 0)
        self.hbox1 = gtk.HBox(False, 0)
        self.vbox1.pack_start(self.scroll, True, True, 1)
        self.hbox1.pack_start(self.searchBar, True, True, 1)
        self.hbox1.pack_start(self.deleteSelectedButton, False, False, 1)
        self.hbox1.pack_start(self.toggleSelectedButton, False, False, 1)
        self.hbox1.pack_start(self.syncAllButton, False, False, 1)
        self.vbox1.pack_start(self.hbox1, False, False, 1)

        # Initialize
        self.dbwindow = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.dbwindow.set_title("SimpleSync")
        self.dbwindow.set_icon_from_file(os.path.join(self.appPath, 'simplesync.png'))
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
        title = None
        if syncSize > 1024:
            syncSize /= 1024.0
            syncSize = '%.2f Gib' % syncSize
        else:
            syncSize = '%.2f Mib' % syncSize

        if len(self.filterModel):
            title = ('SimpleSync - %s: [ %s -> %s ] (%i/%i) (%s)' % (self.dbFile, self.db.sourceDir(), self.db.targetDir(), len(self.filterModel), len(self.listStore), syncSize))
        else:
            title = ('SimpleSync - %s: [ %s -> %s ] (%i) (%s)' % (self.dbFile, self.db.sourceDir(), self.db.targetDir(), len(self.filterModel), syncSize))
        try:
            title = ('(%.1fs) %s' % (self.opTime, title))
        except AttributeError:
            pass
        if self.echo: print title, type(title)
        self.dbwindow.set_title(title)
        
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
        if self.echo: print "Toggle:", toggleList
        if cell != None:
            toggleList = (toggleList,)
        fileList = []
        # Build list of files to set.
        for toggle in toggleList:
            toggle = self.filterModel.convert_path_to_child_path(toggle)
            self.listStore[toggle][6] = not self.listStore[toggle][6]
            fileList.append((self.listStore[toggle][0], self.listStore[toggle][6]))
        self.db.setSync(fileList)
        self.updateTitle()
        return

    def row_callback(self, treeview, row, column):
        '''Call toggle_callback on a row.'''
        selectedRows = self.selectedRows()
        if selectedRows == []:
            self.toggle_callback(True, row)
        else:
            self.toggle_callback(None, selectedRows) 

    def selectedRows(self):
        '''Return list of selected rows by number.'''
        selectedRows = []
        for row in self.tree.get_selection().get_selected_rows()[1:][0]:
            selectedRows.append(row[0])
        return selectedRows

    def deleteSelectedButton_callback(self, button):
        '''Remove selected rows from the DB.'''
        for row in self.selectedRows():
            file = self.filterModel[row][0]
            print "Remove:", file
            self.db.removeFile(self.db.sourceDir(), os.path.join(self.db.sourceDir(), file))
            self.listStore.remove(self.listStore.get_iter(row))
        self.db.connection.commit()

    def column_callback(self, column):
        '''Sort currently viewed tracks by column.'''
        print "Sort by %s." % column.get_title()
        return

    def toggleSelectedButton_callback(self, button):
        '''Toggle sync status of all selected rows.'''
        selectedRows = self.selectedRows()
        if selectedRows == []:
            return
        else:
            self.toggle_callback(None, selectedRows) 

    def syncAllButton_callback(self, button):
        '''Copy marked files from self.targetDir to self.db.sourceDir'''
        sourceDir = self.db.sourceDir()
        targetDir = self.db.targetDir()
        # If we're missing some info, get it!
        while (not sourceDir or not targetDir) and self.editPrefs() == gtk.RESPONSE_OK:
            sourceDir = self.db.sourceDir()
            if not sourceDir:
                self.errorDialog('Specify a source') 
            targetDir = self.db.targetDir()
            if not targetDir:
                self.errorDialog('Specify a target') 
        print "Sync: %s -> %s (%f Mib)" % (sourceDir, targetDir, self.db.syncSize() / 1024.**2)
        for file in self.db.copyList(sourceDir):
            abspath = os.path.join(sourceDir, file).encode('latin-1')
            target = os.path.join(targetDir,file).encode('latin-1')
            print "Sync: ", file
            if not os.path.isdir(os.path.dirname(target)):
                os.makedirs(os.path.dirname(target))
            shutil.copy2(abspath, target)
            self.db.updateFile(sourceDir, abspath)
        self.db.connection.commit()
        self.db.mtime(time.time())
        print "Sync: complete!"
        print "unknownList:", self.db.unknownList(sourceDir)

    def editPrefs(self):
        d = dbPrefsdialog()
        if d.response == gtk.RESPONSE_OK or d.response == gtk.RESPONSE_APPLY:
            dbFile = d.get_Path('DB File')
            if dbFile:
                'editPrefs: got dbFile'
                self.dbFile = dbFile
                self.view(dbFile)
            source = d.get_Path('Source')
            if os.path.isdir(source):
                self.db.sourceDir(source)
                if d.response == gtk.RESPONSE_APPLY:
                        self.db.rebuild()
                        self.db.sourceDir(source)
                        self.opTime = self.db.recurseDir(source, self.db.addFile)
                        self.view(self.dbFile)
            target = d.get_Path('Target')
            if target != '':
                self.db.targetDir(target)
        return d.response

    def openDB(self, dbFile):
        '''Returns a musicDB object connected to dbFile.'''
        return simplesync_db.musicDB(dbFile)

    class errorDialog(gtk.Window):
        '''Pop-up an error displaying msg.'''
        def __init__(self, msg):
            md = gtk.MessageDialog(self,
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_ERROR, 
                                   gtk.BUTTONS_CLOSE,
                                   msg)
            md.run()
            md.destroy()

'''    class threadDBImport(threading.Thread):
        def __init__(self, parent, sourceDir):
            print 'Thread: init'
            self.parent = parent
            self.sourceDir = sourceDir
            threading.Thread.__init__(self)
            print 'Thread: end init'
        def run(self):
            print 'Thread: start'
            #self.parent.db.connection.interrupt()
            db = simplesync_db.musicDB('/tmp/ss3.db')
            db.recurseDir(self.sourceDir, db.updateFile)
            #self.parent.view(self.parent.dbFile)
            print 'Thread: end'
'''

class dbPrefsdialog(gtk.Window):
    '''Dialog box for setting file paths.'''
    def __init__(self):
        self.dialog = gtk.Dialog("File Prefs", self, 0)
        importButton = self.dialog.add_button(gtk.STOCK_SAVE_AS, gtk.RESPONSE_APPLY)
        importButton.set_label('_Import')
        importButton.set_image(gtk.image_new_from_stock('gtk-save-as', gtk.ICON_SIZE_BUTTON))
        cancelButton = self.dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        okButton = self.dialog.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.dialog.action_area.set_layout(gtk.BUTTONBOX_EDGE)
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
        return os.path.expanduser(self.fileEntryGroups[name].get_text())

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
