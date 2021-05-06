#!/bin/env python3

import configparser
import re
import sys
import tempfile
import os
import magic
import io
from elftools.elf.elffile import ELFFile
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

def reset_view(msg):
    global opk_path
    opk_path = ""
    textbuffer.set_text(msg)

# initialization
reset_view("Load an OPK file to see its description.")

def extract_node(node, destpath):
    if node.isFolder():
        if node.getName() == "":
            dirpath = destpath
        else:
            dirpath = destpath + "/" + node.getName().decode("utf-8")
            os.mkdir(dirpath)
        for c in node.children:
            extract_node(c, dirpath)
    else:
        with open(destpath + "/" + node.getName().decode("utf-8"), "wb") as f:
            f.write(node.getContent())

def extract_opk(path, dest):
    opk = SquashFsImage(path)
    extract_node(opk.getRoot(), dest)

def load_opk(path):
    global opk_path
    opk_path = path
    filename = path
    opk = SquashFsImage(path)
    image.clear()
    platformset = set()
    desktopno = 0
    platforms = ""
    desktops = dict()
    manuals = dict()
    execs = dict()
    for i in opk.root.children:
        iname = i.getName().decode("utf-8")
        m = re.match(r"(?:[^.]*\.)?([^.]+)\.desktop", iname)
        if m is not None:
            desktopno = desktopno + 1
            desktopfile = configparser.ConfigParser(allow_no_value=True, strict=False)
            desktopfile.read_string(i.getContent().decode("utf-8"))
            dset = dict()
            dset['appname'] = desktopfile["Desktop Entry"].get("Name", "", raw=True)
            dset['executable'] = os.path.basename(desktopfile["Desktop Entry"].get("Exec", "", raw=True).split()[0])
            if dset['executable'] != "":
                execs[dset['executable']] = dict()
            else:
                dset['executable'] = "<none>"
            dset['version'] = desktopfile["Desktop Entry"].get("Version", "", raw=True)
            dset['comment'] = desktopfile["Desktop Entry"].get("Comment", "", raw=True)
            dset['manualpath'] = desktopfile["Desktop Entry"].get("X-OD-Manual", "", raw=True)
            if dset['manualpath'] != "":
                manuals[dset['manualpath']] = ""
            desktops[iname] = dset
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
        if iname in manuals:
            encodings = ["utf-8", "latin_1", "iso8859_2", "cp1250", "cp1252", "utf-16", "utf-32"]
            man = ""
            for e in encodings:
                try:
                    manuals[iname] = i.getContent().decode(e)
                    break
                except:
                    manuals[iname] = "<reading error>"
        if iname in execs:
            execs[iname]['magic'] = magic.from_buffer(i.getContent())
            execs[iname]['mime'] = magic.from_buffer(i.getContent(), mime=True)
            execs[iname]['iself'] = execs[iname]['mime'] == 'application/x-executable' or execs[iname]['mime'] == 'application/x-pie-executable'
            if execs[iname]['iself']:
                bstream = io.BytesIO(i.getContent())
                elf = ELFFile(bstream)
                dynsec = elf.get_section_by_name(".dynamic")
                execs[iname]['dynamic'] = dynsec is not None
                if execs[iname]['dynamic']:
                    execs[iname]['deps'] = []
                    for tag in dynsec.iter_tags():
                        if tag.entry.d_tag == "DT_NEEDED":
                            execs[iname]['deps'].append(tag.needed)
    opk.close()
    if platforms == "":
        platforms = "none"
    content = "OPK filename: " + filename + "\n"
    content += "Number of desktop files: " + str(desktopno) + "\n"
    content += "Platforms: " + platforms + "\n\n"
    for key in desktops:
        content += "Desktop file: " + key + "\n"
        if desktops[key]['appname'] == "":
            desktops[key]['appname'] = "none"
        content += "Appname: " + desktops[key]['appname'] + "\n"
        content += "Executable: " + desktops[key]['executable'] + "\n"
        if desktops[key]['version'] != "":
            content += "Version: " + desktops[key]['version'] + "\n"
        if desktops[key]['comment'] != "":
            content += "Comment: " + desktops[key]['comment'] + "\n"
        if desktops[key]['manualpath'] != "":
            content += "Manual: " + desktops[key]['manualpath'] + "\n"
        content += "\n"
    for key in execs:
        content += "Executable " + key + "\n"
        content += "Identity: " + execs[key]['magic'] + "\n"
        if execs[key]['iself']:
            if execs[key]['dynamic']:
                content += "The executable is dynamically linked.\n"
                if len(execs[key]['deps']) == 0:
                    content += "No dynamic dependencies detected.\n"
                else:
                    content += "Dynamic dependencies:\n"
                    for d in execs[key]['deps']:
                        content += "    " + d + "\n"
            else:
                content += "The executable is statically linked.\n"
        content += "\n"
    for key in manuals:
        if manuals[key] == "":
            content += "Manual " + key + " is empty or nonexistent.\n"
        else:
            content += "Manual " + key + "\n"
            content += "=== MANUAL START ===\n"
            content += manuals[key] + "\n"
            content += "=== MANUAL END ===\n"
            content += "\n"
    textbuffer.set_text(content)

class Handler:
    def onDestroy(self, *args):
        Gtk.main_quit()

    def onOpen(self, *args):
        dialog = Gtk.FileChooserDialog("Select an OPK file", window,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            try:
                load_opk(filepath)
            except:
                reset_view("OPK loading failed.")
        dialog.destroy()

    def onExtract(self, *args):
        dialog = Gtk.FileChooserDialog("Select a destination folder", window,
            Gtk.FileChooserAction.SELECT_FOLDER,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            if opk_path != "":
                extract_opk(opk_path, filepath)
        dialog.destroy()

    def onAbout(self, *args):
        aboutdialog.show()

    def onAboutDialogClose(self, *args):
        aboutdialog.hide()

builder.connect_signals(Handler())

if len(sys.argv) == 2:
	load_opk(sys.argv[1])
Gtk.main()
