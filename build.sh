#!/bin/sh
# Package TypMaths as a LibreOffice extension (.oxt).
#
# Usage: ./build.sh   ->  creates TypMaths.oxt in this directory.
# Install with: soffice --install-extension TypMaths.oxt
#               or via Tools > Extension Manager > Add.
set -e
cd "$(dirname "$0")"

rm -f TypMaths.oxt

zip -r -X TypMaths.oxt \
    META-INF \
    description.xml \
    description_en.txt \
    Addons.xcu \
    icons \
    Scripts \
    -x '*__pycache__*' '*.pyc'

echo "Created $(pwd)/TypMaths.oxt"
