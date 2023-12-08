/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/bluetooth/bluetooth.h>

void evt_ready(void);

int main(void)
{
	printk("RPC testing app started [APP Core].\n");

	bt_enable(NULL);
	printk("bt enabled\n");

	/* Signal to python testcase that we are ready to accept commands. */
	evt_ready();

	printk("evt_ready sent\n");

	return 0;
}
