# TypMaths – Typst Equation Editor for LibreOffice

Write mathematical equations in [Typst](https://typst.app) markup directly inside
LibreOffice. The equation is compiled to SVG by the Typst CLI and inserted at the
cursor in Writer documents (or centered on slides in Impress/Draw). Selecting an
existing equation image and running the extension again re-opens its source code
for in-place editing.

- Extension identifier: **org.yongwang.typmaths**
- Version: **1.2.0**
- Author: Yong Wang

## Requirements

- LibreOffice (Writer / Impress / Draw)
- Python scripting support bundled with LibreOffice
- The Typst CLI (`typst`) available on the system `PATH`

## Layout

```
META-INF/manifest.xml      package manifest
description.xml            extension metadata (identifier org.yongwang.typmaths)
description_en.txt         license/description shown in the Extension Manager
Addons.xcu                 toolbar button + icon registration
Scripts/python/TypMaths.py implementation:
                           - UNO component  org.yongwang.typmaths.TypMathsJob
                             (triggered by the toolbar button)
                           - exported macro typmaths() (g_exportedScripts),
                             assignable to a keyboard shortcut
icons/                     toolbar icons
build.sh                   packages everything into TypMaths.oxt
```

> **Do not remove** the `application/vnd.sun.star.framework-script` entry for
> `Scripts/python` from `META-INF/manifest.xml`: without it LibreOffice still
> runs the toolbar job but silently hides the macro from *Tools > Customize >
> Keyboard*, making shortcut assignment impossible.

## Build & install

```sh
./build.sh                       # produces TypMaths.oxt
soffice --install-extension TypMaths.oxt
```

or add `TypMaths.oxt` through *Tools ▸ Extension Manager ▸ Add*, then restart
LibreOffice.

> **Upgrading from versions older than 1.2.0:** the identifier changed from
> `org.typmaths.addon` to `org.yongwang.typmaths`, so remove the old version in
> the Extension Manager first, otherwise both will show up side by side.

## Using it

**Toolbar:** click the *TypMaths* button, type Typst markup such as
`x^2 = y / z`, set the font size, press *Insert*. Select an inserted equation and
click the button again to edit it.

**Dialog shortcuts:** `Ctrl+Enter` is equivalent to clicking *Insert / Update*
(works with focus in any field of the dialog); `Esc` cancels. Plain `Enter` in
the multi-line code field still types a newline.

**Keyboard shortcut:** the extension publishes a macro named `typmaths` which does
exactly the same thing. Assign a key to it once:

1. *Tools ▸ Customize…* → *Keyboard* tab.
2. Category: **LibreOffice Macros**.
3. Browse to your installation (`user` or `share`), then
   *TypMaths* → *TypMaths.py* → **typmaths**.
4. Choose a key combination in *Shortcut keys* and press **Modify**.

The macro can also be run from *Tools ▸ Macros ▸ Run Macro…*
