import uno
import unohelper
import json
import os
import tempfile
import subprocess
import shutil
import re
import traceback
from com.sun.star.task import XJobExecutor
from com.sun.star.awt.PushButtonType import OK, CANCEL
from com.sun.star.beans import PropertyValue
from com.sun.star.text.TextContentAnchorType import AS_CHARACTER
from com.sun.star.awt import Size, Point, XKeyListener
from com.sun.star.awt.Key import RETURN
from com.sun.star.awt.KeyModifier import MOD1

def get_svg_dimensions(filepath):
    """Return the native (width, height) of an SVG file, converted to points."""
    fallback = (40.0, 14.0)
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(4096)
        root = re.search(r'<svg\b[^>]*>', head, re.IGNORECASE | re.DOTALL)
        if not root:
            return fallback
        tag = root.group(0)

        unit_to_pt = {
            '': 1.0,
            'pt': 1.0,
            'px': 72.0 / 96.0,
            'mm': 72.0 / 25.4,
            'cm': 720.0 / 25.4,
            'in': 72.0,
        }

        def length_to_pt(raw):
            m = re.match(r'\s*([+-]?\d+(?:\.\d+)?)\s*([a-z%]*)\s*$', raw)
            if not m:
                return None
            factor = unit_to_pt.get(m.group(2))
            return float(m.group(1)) * factor if factor is not None else None

        def attr_len(name):
            m = re.search(r'\b%s\s*=\s*"([^"]*)"' % name, tag, re.IGNORECASE)
            if m:
                value = length_to_pt(m.group(1))
                if value is not None and value > 0:
                    return value
            return None

        width = attr_len('width')
        height = attr_len('height')

        # Fall back to the viewBox (Typst emits user units equal to points)
        if width is None or height is None:
            vb = re.search(
                r'\bviewBox\s*=\s*"\s*([-\d.eE+]+)[ ,]+([-\d.eE+]+)'
                r'[ ,]+([-\d.eE+]+)[ ,]+([-\d.eE+]+)', tag)
            if vb:
                if width is None:
                    width = float(vb.group(3))
                if height is None:
                    height = float(vb.group(4))

        if width is not None and height is not None \
                and width > 0 and height > 0:
            return width, height
    except Exception:
        pass
    return fallback

def show_message_box(ctx, title, message, box_type="infobox"):
    try:
        smgr = ctx.ServiceManager
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        parent = toolkit.getDesktopWindow()
        # com.sun.star.awt.MessageBoxButtons.BUTTONS_OK = 1
        mb = toolkit.createMessageBox(parent, box_type, 1, title, message)
        mb.execute()
    except Exception:
        pass

class CtrlEnterActivator(unohelper.Base, XKeyListener):
    """Close the given dialog with result 1 (= OK) on Ctrl+Enter.

    Attached to the equation editor's fields so users can Insert/Update
    without leaving the keyboard. Plain Enter is untouched (it keeps
    typing a newline inside the multi-line code field).
    """

    def __init__(self, dialog):
        self._dialog = dialog

    def keyPressed(self, event):
        try:
            if event.KeyCode == RETURN and (event.Modifiers & MOD1):
                self._dialog.endDialog(1)
        except Exception:
            pass

    def keyReleased(self, event):
        pass

    def disposing(self, *args):
        pass


def show_typst_dialog(ctx, initial_text="", initial_size="12"):
    smgr = ctx.ServiceManager
    dialog_model = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dialog_model.PositionX = 150
    dialog_model.PositionY = 150
    dialog_model.Width = 320
    dialog_model.Height = 185
    dialog_model.Title = "TypMaths - Typst Equation Editor"

    # Label
    label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label_model.Name = "Label"
    label_model.Label = "Enter Typst equation code (e.g. x = y^2 / z):"
    label_model.PositionX = 10
    label_model.PositionY = 10
    label_model.Width = 300
    label_model.Height = 15
    dialog_model.insertByName("Label", label_model)

    # Edit Box
    edit_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
    edit_model.Name = "CodeField"
    edit_model.Text = initial_text
    edit_model.PositionX = 10
    edit_model.PositionY = 30
    edit_model.Width = 300
    edit_model.Height = 80
    edit_model.MultiLine = True
    edit_model.AutoVScroll = True
    edit_model.HardLineBreaks = True
    dialog_model.insertByName("CodeField", edit_model)

    # Font Size Label
    size_label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    size_label_model.Name = "SizeLabel"
    size_label_model.Label = "Font Size (pt):"
    size_label_model.PositionX = 10
    size_label_model.PositionY = 120
    size_label_model.Width = 80
    size_label_model.Height = 15
    dialog_model.insertByName("SizeLabel", size_label_model)

    # Font Size Edit Box
    size_edit_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
    size_edit_model.Name = "SizeField"
    size_edit_model.Text = initial_size
    size_edit_model.PositionX = 90
    size_edit_model.PositionY = 118
    size_edit_model.Width = 50
    size_edit_model.Height = 18
    dialog_model.insertByName("SizeField", size_edit_model)

    # OK Button
    ok_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok_model.Name = "OKBtn"
    ok_model.Label = "Update" if initial_text else "Insert"
    ok_model.PositionX = 150
    ok_model.PositionY = 155
    ok_model.Width = 75
    ok_model.Height = 20
    ok_model.PushButtonType = OK
    # Enter in the single-line size field (and Ctrl+Enter via the key
    # listener below) activates this button.
    ok_model.DefaultButton = True
    dialog_model.insertByName("OKBtn", ok_model)

    # Cancel Button
    cancel_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel_model.Name = "CancelBtn"
    cancel_model.Label = "Cancel"
    cancel_model.PositionX = 235
    cancel_model.PositionY = 155
    cancel_model.Width = 75
    cancel_model.Height = 20
    cancel_model.PushButtonType = CANCEL
    dialog_model.insertByName("CancelBtn", cancel_model)

    # Create dialog control
    dlg = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dlg.setModel(dialog_model)

    # Create a Peer to display
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dlg.createPeer(toolkit, None)

    # Ctrl+Enter anywhere in the dialog acts like pressing Insert/Update
    ctrl_enter = CtrlEnterActivator(dlg)
    for _name in ("CodeField", "SizeField"):
        try:
            dlg.getControl(_name).getPeer().addKeyListener(ctrl_enter)
        except Exception:
            pass
    try:
        dlg.getPeer().addKeyListener(ctrl_enter)
    except Exception:
        pass

    res = dlg.execute()
    entered_text = None
    entered_size = None
    if res == 1:
        code_ctrl = dlg.getControl("CodeField")
        entered_text = code_ctrl.getText()
        size_ctrl = dlg.getControl("SizeField")
        entered_size = size_ctrl.getText()
        
    dlg.dispose()
    return entered_text, entered_size

class TypMathsJob(unohelper.Base, XJobExecutor):
    """UNO component behind the toolbar button.

    Instantiated when LibreOffice dispatches
    "service:org.yongwang.typmaths.TypMathsJob?execute" (see Addons.xcu);
    the trailing "?execute" argument arrives in trigger().
    """

    def __init__(self, ctx):
        self.ctx = ctx
        
    def trigger(self, event):
        if event == "execute":
            self.run()
            
    def get_selected_image(self, doc):
        try:
            selection = doc.getCurrentController().getSelection()
            if not selection:
                return None
            if hasattr(selection, "supportsService"):
                if selection.supportsService("com.sun.star.text.TextGraphicObject") or selection.supportsService("com.sun.star.drawing.GraphicObjectShape"):
                    return selection
            if hasattr(selection, "getCount") and selection.getCount() > 0:
                item = selection.getByIndex(0)
                if hasattr(item, "supportsService"):
                    if item.supportsService("com.sun.star.text.TextGraphicObject") or item.supportsService("com.sun.star.drawing.GraphicObjectShape"):
                        return item
        except Exception:
            pass
        return None

    def run(self):
        try:
            desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            doc = desktop.getCurrentComponent()
            if not doc:
                show_message_box(self.ctx, "TypMaths", "No active document found.", "errorbox")
                return
            
            # Detect selection for in-place edit
            selected_img = self.get_selected_image(doc)
            initial_text = ""
            initial_size = "12"
            if selected_img:
                desc = selected_img.Description or ""
                if desc.startswith("typst-json:"):
                    try:
                        data = json.loads(desc[len("typst-json:"):])
                        initial_text = data.get("code", "")
                        initial_size = str(data.get("size", "12"))
                    except Exception:
                        pass
                elif desc.startswith("typst:"):
                    initial_text = desc[len("typst:"):].strip()
                    initial_size = "12"
                    
            entered_text, entered_size = show_typst_dialog(self.ctx, initial_text, initial_size)
            if entered_text is None:
                return # Cancelled
                
            entered_text = entered_text.strip()
            if not entered_text:
                return
                
            entered_size = entered_size.strip() if entered_size else "12"
            try:
                font_size = float(entered_size)
                if font_size <= 0:
                    font_size = 12.0
            except ValueError:
                font_size = 12.0
                
            typst_equation = entered_text
            if not typst_equation.startswith('$'):
                typst_equation = f"$ {typst_equation} $"
                
            # Compile using Typst
            tmp_dir = tempfile.mkdtemp()
            try:
                typ_path = os.path.join(tmp_dir, "equation.typ")
                svg_path = os.path.join(tmp_dir, "equation.svg")
                
                typst_code = f"""#set page(width: auto, height: auto, margin: 2pt, fill: none)
#set text(size: {font_size}pt)
#show math.equation: set text(top-edge: "bounds", bottom-edge: "bounds")
{typst_equation}
"""
                with open(typ_path, "w", encoding="utf-8") as f:
                    f.write(typst_code)
                    
                # Run Typst CLI compilation to SVG (resolution-independent vector)
                process = subprocess.run(
                    ["typst", "compile", typ_path, svg_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if process.returncode != 0:
                    show_message_box(self.ctx, "TypMaths - Compilation Error", process.stderr, "errorbox")
                    return
                    
                if not os.path.exists(svg_path):
                    show_message_box(self.ctx, "TypMaths - Error", "SVG output was not generated.", "errorbox")
                    return
                    
                # Read the SVG native size (points) to size the UNO Graphic
                width_pt, height_pt = get_svg_dimensions(svg_path)
                
                # 1 pt = 25.4 / 72 mm  ->  size in 1/100 mm:
                # size_100th_mm = pt * 2540 / 72
                width_100th_mm = int(round((width_pt * 2540) / 72.0))
                height_100th_mm = int(round((height_pt * 2540) / 72.0))
                
                # Load SVG as UNO Graphic object using GraphicProvider
                provider = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.graphic.GraphicProvider", self.ctx)
                prop = PropertyValue()
                prop.Name = "URL"
                prop.Value = uno.systemPathToFileUrl(svg_path)
                graphic = provider.queryGraphic((prop,))
                
                desc_data = {
                    "code": entered_text,
                    "size": font_size
                }
                desc_text = "typst-json:" + json.dumps(desc_data)
                
                if selected_img:
                    # Update existing image in-place
                    selected_img.Graphic = graphic
                    selected_img.Description = desc_text
                    if selected_img.supportsService("com.sun.star.text.TextGraphicObject"):
                        selected_img.Width = width_100th_mm
                        selected_img.Height = height_100th_mm
                    elif selected_img.supportsService("com.sun.star.drawing.GraphicObjectShape"):
                        selected_img.setSize(Size(width_100th_mm, height_100th_mm))
                else:
                    # Insert new image
                    if doc.supportsService("com.sun.star.text.TextDocument"):
                        image = doc.createInstance("com.sun.star.text.TextGraphicObject")
                        image.Graphic = graphic
                        image.Description = desc_text
                        image.AnchorType = AS_CHARACTER
                        image.Width = width_100th_mm
                        image.Height = height_100th_mm
                        
                        controller = doc.getCurrentController()
                        view_cursor = controller.getViewCursor()
                        text = view_cursor.getText()
                        text.insertTextContent(view_cursor, image, False)
                        
                    elif doc.supportsService("com.sun.star.presentation.PresentationDocument") or doc.supportsService("com.sun.star.drawing.DrawingDocument"):
                        image = doc.createInstance("com.sun.star.drawing.GraphicObjectShape")
                        image.Graphic = graphic
                        image.Description = desc_text
                        
                        controller = doc.getCurrentController()
                        draw_page = controller.getCurrentPage()
                        draw_page.add(image)
                        
                        image.setSize(Size(width_100th_mm, height_100th_mm))
                        
                        # Center the image on the slide page
                        slide_w = draw_page.Width
                        slide_h = draw_page.Height
                        pos_x = (slide_w - width_100th_mm) // 2
                        pos_y = (slide_h - height_100th_mm) // 2
                        image.setPosition(Point(pos_x, pos_y))
                    else:
                        show_message_box(self.ctx, "TypMaths - Unsupported Document", "This document type is not supported.", "errorbox")
            finally:
                shutil.rmtree(tmp_dir)
        except Exception:
            show_message_box(self.ctx, "TypMaths - Python Error", traceback.format_exc(), "errorbox")

def run_typmaths(ctx):
    """Run the equation editor for the given component context."""
    TypMathsJob(ctx).run()


def typmaths(*args):
    """TypMaths macro entry point.

    Published by the Scripting Framework as a macro named "typmaths", so it
    can be assigned a keyboard shortcut via Tools > Customize > Keyboard
    (category "LibreOffice Macros") or run from Tools > Macros.

    When invoked by the scripting framework, args[0] is the XScriptContext;
    any other way of calling it falls back to the running office context.
    """
    ctx = None
    for arg in args:
        getter = getattr(arg, "getComponentContext", None)
        if callable(getter):
            ctx = getter()
            break
    if ctx is None:
        ctx = uno.getComponentContext()
    run_typmaths(ctx)


# Functions listed here are exported to the Scripting Framework and become
# visible as macros ("LibreOffice Macros" in Tools > Macros and in the
# Keyboard tab of Tools > Customize, where shortcuts can be assigned).
g_exportedScripts = (typmaths,)

g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    TypMathsJob,
    "org.yongwang.typmaths.TypMathsJob",
    ("com.sun.star.task.Job",),
)
