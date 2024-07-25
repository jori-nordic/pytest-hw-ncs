/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/bluetooth/bluetooth.h>

void evt_ready(void);
extern void register_handlers(void);
int main(void)
{
	printk("RPC testing app started [APP Core].\n");

	bt_enable(NULL);
	printk("bt enabled\n");

	register_handlers();

	evt_ready();

	return 0;
}
