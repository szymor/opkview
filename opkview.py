#!/bin/env python3

import configparser
import re
import sys
import tempfile
import magic
from PySquashfsImage import SquashFsImage
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf

builder = Gtk.Builder()
builder.add_from_file("layout.glade")
window = builder.get_object("window1")
window.set_title("Tiny OPK Viewer")
window.show_all()
textview = builder.get_object("textview1")
textbuffer = textview.get_buffer()
image = builder.get_object("image1")
aboutdialog = builder.get_object('aboutdialog1')

# initialization
textbuffer.set_text("to be loaded")

def load_opk(path):
    filename = path
    opk = SquashFsImage(path)
    image.clear()
    platformset = set()
    desktopno = 0
    platforms = ""
    appname = ""
    executable = ""
    execid = ""
    version = ""
    comment = ""
    manual = ""
    manualpath = ""
    for i in opk.root.children:
        iname = i.getName().decode("utf-8")
        m = re.match(r"(?:[^.]*\.)?([a-zA-Z0-9]+)\.desktop", iname)
        if m is not None:
            desktopno = desktopno + 1
            if len(platformset) == 0:
                # parse .desktop file once
                desktopfile = configparser.ConfigParser(allow_no_value=True, strict=False)
                desktopfile.read_string(i.getContent().decode("utf-8"))
                appname = desktopfile["Desktop Entry"].get("Name", "")
                executable = desktopfile["Desktop Entry"].get("Exec", "<none>")
                version = desktopfile["Desktop Entry"].get("Version", "")
                comment = desktopfile["Desktop Entry"].get("Comment", "")
                manualpath = desktopfile["Desktop Entry"].get("X-OD-Manual", "")
            platformset.add(m.group(1))
        m = re.match(r".+\.png", iname)
        if m is not None:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(i.getContent())
            loader.close()
            image.set_from_pixbuf(loader.get_pixbuf())
    # convert platform set to string
    for p in platformset:
        if platforms == "":
            platforms += p
        else:
            platforms += ", " + p
    for i in opk.root.children:
        iname = i.getName().decode("utf-8")
        if iname == manualpath:
            encodings = ["utf-8", "latin_1", "iso8859_2", "cp1250", "cp1252", "utf-16", "utf-32"]
            for e in encodings:
                try:
                    manual = i.getContent().decode(e)
                    break
                except:
                    manual = "<reading error>"
        if iname == executable:
            # workaround for libmagic from_file vs from_buffer bug for elves
            with tempfile.NamedTemporaryFile() as f:
                f.write(i.getContent())
                execid = magic.from_file(f.name)
    opk.close()
    if appname == "":
        appname = "none"
    if platforms == "":
        platforms = "none"
    content = "OPK filename: " + filename + "\n"
    content += "Number of desktop files: " + str(desktopno) + "\n"
    content += "Platforms: " + platforms + "\n\n"
    content += "Appname: " + appname + "\n"
    content += "Executable: " + executable + "\n"
    content += "Exec identity: " + execid + "\n"
    if version != "":
        content += "Version: " + version + "\n"
    if comment != "":
        content += "Comment: " + comment + "\n"
    if manual != "":
        content += "\nManual:\n" + manual
    textbuffer.set_text(content)

class Handler:
    def onDestroy(self, *args):
        Gtk.main_quit()

    def onOpen(self, *args):
        dialog = Gtk.FileChooserDialog("Please choose a file", window,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            load_opk(filepath)
        dialog.destroy()

    def onAbout(self, *args):
        aboutdialog.show()

    def onAboutDialogClose(self, *args):
        aboutdialog.hide()

builder.connect_signals(Handler())

if len(sys.argv) == 2:
	load_opk(sys.argv[1])
Gtk.main()
