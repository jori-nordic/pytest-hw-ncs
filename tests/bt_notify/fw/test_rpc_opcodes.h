/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#ifndef RPC_OPCODES_H_
#define RPC_OPCODES_H_

enum command_opcodes {
	RPC_COMMAND_BT_SCAN = 0x01,
	RPC_COMMAND_BT_ADVERTISE,
	RPC_COMMAND_BT_CONNECT,
	RPC_COMMAND_BT_DISCONNECT,
};

enum event_opcodes {
	RPC_EVENT_READY= 0x01,
	RPC_EVENT_BT_CONNECTED,
	RPC_EVENT_BT_DISCONNECTED,
	RPC_EVENT_BT_SCAN_REPORT,
	RPC_EVENT_DEMO_NESTED_LIST,

	RPC_ASYNC_BT_ADVERTISE,
	RPC_ASYNC_BT_SCAN,
	RPC_ASYNC_BT_SCAN_STOP,
	RPC_ASYNC_BT_CONNECT,
	RPC_ASYNC_BT_DISCONNECT,

	RPC_ASYNC_K_OOPS,
};

#endif /* RPC_OPCODES_H_ */
