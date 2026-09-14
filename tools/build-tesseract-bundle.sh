#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT=/opt/tesseract-bookworm
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

sudo apt-get update
sudo apt-get install -y debootstrap

if [ ! -x "$BUNDLE_ROOT/usr/bin/tesseract" ]; then
    sudo debootstrap --arch=amd64 bookworm "$BUNDLE_ROOT" \
        https://deb.debian.org/debian
fi

sudo chroot "$BUNDLE_ROOT" apt-get update
sudo chroot "$BUNDLE_ROOT" apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng

sudo chroot "$BUNDLE_ROOT" /bin/bash <<'CHROOT_BASH'
set -euo pipefail

rm -rf /ocr-bundle
mkdir -p /ocr-bundle/bin /ocr-bundle/lib /ocr-bundle/tessdata /ocr-bundle/licenses

cp /usr/bin/tesseract /ocr-bundle/bin/tesseract.bin
ldd /usr/bin/tesseract > /ocr-bundle/dependencies.txt

if grep -q "not found" /ocr-bundle/dependencies.txt; then
    cat /ocr-bundle/dependencies.txt
    exit 1
fi

awk '/=> \/\// {print $3} /^[[:space:]]*\// {print $1}' /ocr-bundle/dependencies.txt |
while read -r library; do
    cp -L "$library" /ocr-bundle/lib/
done

cp -L /lib64/ld-linux-x86-64.so.2 /ocr-bundle/lib/
cp /usr/share/tesseract-ocr/5/tessdata/*.traineddata /ocr-bundle/tessdata/

for directory in /usr/share/doc/*; do
    if [ -f "$directory/copyright" ]; then
        cp "$directory/copyright" \
            "/ocr-bundle/licenses/$(basename "$directory").copyright"
    fi
done
CHROOT_BASH

sudo tee "$BUNDLE_ROOT/ocr-bundle/bin/tesseract" > /dev/null <<'LAUNCHER'
#!/bin/sh
set -eu

OCR_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
export TESSDATA_PREFIX="$OCR_DIR/tessdata"

exec "$OCR_DIR/lib/ld-linux-x86-64.so.2" \
    --library-path "$OCR_DIR/lib" \
    "$OCR_DIR/bin/tesseract.bin" "$@"
LAUNCHER
sudo chmod +x "$BUNDLE_ROOT/ocr-bundle/bin/tesseract"

mkdir -p "$PROJECT_DIR/tools"
sudo tar -czf "$PROJECT_DIR/tools/tesseract-linux-amd64.tar.gz" \
    -C "$BUNDLE_ROOT/ocr-bundle" .

echo "Created $PROJECT_DIR/tools/tesseract-linux-amd64.tar.gz"