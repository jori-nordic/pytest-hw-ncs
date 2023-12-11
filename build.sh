#!/usr/bin/env bash
#
# Run this script with the same filter arguments as pytest.
# It will build the FW for all the tests that are returned by pytest.

# Fail the whole build on the first error
set -e

TEST_LIST_FILE=build/testlist.txt
ZEPHYR_BOARDS=('nrf52840dk_nrf52840')

# rm -rf build || true
mkdir -p build

pytest --collect-only "$@" | grep Module | sed -E 's/<Module (.*)>/\1/' > "$TEST_LIST_FILE"

while read -r line; do
    for board in "${ZEPHYR_BOARDS[@]}"; do
        BUILD_DIR=build/$(dirname "$line")/${board}
        SRC_DIR=$(dirname "$line")/fw
        echo "building firmware for $line in $BUILD_DIR"
        west build -b "$board" -d "$BUILD_DIR" "$SRC_DIR"
    done
done < "$TEST_LIST_FILE"
