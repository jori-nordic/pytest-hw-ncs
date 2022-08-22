/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <bluetooth/bluetooth.h>
#include <nrf_rpc.h>

#include "rpc_handler.h"

void evt_ready(void);
void evt_scan_report(void);

void main(void)
{
	printk("RPC testing app started [APP Core].\n");

	bt_enable(NULL);
	printk("bt enabled\n");

	/* Signal to python testcase that we are ready to accept commands. */
	evt_ready();

	printk("evt_ready sent\n");

	/* TODO: use an actual scan report */
	k_msleep(2000);
	evt_scan_report();
	printk("evt_scan_report sent\n");
}
