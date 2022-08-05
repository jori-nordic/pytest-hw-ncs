/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <nrf_rpc.h>

#include "rpc_handler.h"

void main(void)
{
	printk("RPC testing app started [APP Core].\n");

	/* Signal to python testcase that we are ready to accept commands. */
	evt_ready();

	printk("evt_ready sent\n");
}
