/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#ifndef RPC_OPCODES_H_
#define RPC_OPCODES_H_

enum command_opcodes {
	RPC_COMMAND_BT_CONNECT = 0x01,
	RPC_COMMAND_BT_DISCONNECT,
	RPC_COMMAND_BT_NOTIFY,
};

enum event_opcodes {
	RPC_EVENT_READY= 0x01,
	RPC_EVENT_BT_CONNECTED,
	RPC_EVENT_BT_DISCONNECTED,
	RPC_EVENT_NOTIFICATION_RECEIVED,
};

#endif /* RPC_OPCODES_H_ */
