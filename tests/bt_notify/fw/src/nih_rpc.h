/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */
/* TODO: naming n stuff */
#ifndef NIH_RPC_UART_H_
#define NIH_RPC_UART_H_

#include <zephyr/device.h>

#include <zephyr/sys/ring_buffer.h>
#include <zephyr/net/buf.h>

#include <stdbool.h>

enum nih_rpc_packet_types {
	RPC_TYPE_INIT = 0,
	RPC_TYPE_INITRSP,
	RPC_TYPE_CMD,
	RPC_TYPE_RSP,
	RPC_TYPE_EVT,
	RPC_TYPE_ACK,
	RPC_TYPE_ERR,
	RPC_TYPE_LOG,
	RPC_TYPE_MAX,
};

struct nih_rpc_header {
	uint8_t type;
	uint16_t opcode;
};

/* We have to use an additional header because the nRF RPC header
 * does not encode packet length information.
 */
struct nih_rpc_uart_header {
	char start[4];		/* spells U A R T */
	uint16_t len;
	uint8_t crc;		/* CRC of whole frame */
};

#define NIH_RPC_BUF_RESERVE (sizeof(struct nih_rpc_header) + sizeof(struct nih_rpc_uart_header))

enum nih_rpc_uart_state {
	NSTATE_RFU = 0,
	NSTATE_UNINITIALIZED,
	NSTATE_INITIALIZING,
	NSTATE_INITIALIZED,
	NSTATE_LAST,
};

struct nih_rpc_uart {
	const struct device *uart;

	/** Indicates if transport is already initialized. */
	enum nih_rpc_uart_state state;

	/* Current index, used when building header */
	uint8_t idx;

	struct nih_rpc_uart_header *header;

	/* ring buffer: stores all received uart data */
	struct ring_buf *ringbuf;

	/* packet buffer: stores only the packet to be sent to nRF RPC */
	char *packet;

	/* Thread-safety */
	struct k_mutex mutex;

	/* Dispatches callbacks into nRF RPC */
	struct k_work work;
};

typedef int (*nih_rpc_handler_t)(struct net_buf *buf);

void nih_rpc_register_cmd_handlers(nih_rpc_handler_t handlers[], size_t num);
void nih_rpc_register_evt_handlers(nih_rpc_handler_t handlers[], size_t num);
int nih_rpc_send_rsp(struct net_buf *buf, uint16_t opcode);
int nih_rpc_send_event(struct net_buf *buf, uint16_t opcode);
int nih_rpc_send_log(struct net_buf *buf);
bool nih_rpc_is_available(void);
struct net_buf *nih_rpc_alloc_buf(size_t size);

#define NIH_RPC_LOG_LEVEL 0

#endif /* NIH_RPC_UART_H_ */
