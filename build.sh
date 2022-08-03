#!/usr/bin/env bash
#
# Run this script with the same filter arguments as pytest.
# It will build the FW for all the tests that are returned by pytest.

TEST_LIST_FILE=build/testlist.txt
ZEPHYR_BOARD=nrf5340dk_nrf5340_cpuapp

mkdir -p build

pytest --collect-only "$@" | grep Module | sed -E 's/<Module (.*)>/\1/' > "$TEST_LIST_FILE"

while read -r line; do
    BUILD_DIR=build/$(dirname "$line")
    SRC_DIR=$(dirname "$line")/fw
    echo "building firmware for $line in $BUILD_DIR"
    west build -b "$ZEPHYR_BOARD" -d "$BUILD_DIR" "$SRC_DIR"
done < "$TEST_LIST_FILE"
