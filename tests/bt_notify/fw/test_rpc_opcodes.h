/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#ifndef RPC_OPCODES_H_
#define RPC_OPCODES_H_

/* Right now, those are only used for Target -> PC communication.
 * They could also be used for async PC -> Target commands later.
 */
enum event_opcodes {
	RPC_EVENT_READY= 0x01,
	RPC_EVENT_BT_CONNECTED,
	RPC_EVENT_BT_DISCONNECTED,
	RPC_EVENT_BT_SCAN_REPORT,
	RPC_EVENT_DEMO_NESTED_LIST,
	RPC_EVT_MAX,
};

enum cmd_opcodes {
	RPC_CMD_BT_ADVERTISE = 0x01,
	RPC_CMD_BT_SCAN,
	RPC_CMD_BT_SCAN_STOP,
	RPC_CMD_BT_CONNECT,
	RPC_CMD_BT_DISCONNECT,

	RPC_CMD_K_OOPS,
	RPC_CMD_MAX,
};

#endif /* RPC_OPCODES_H_ */
