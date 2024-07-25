/*
 * Copyright (c) 2024 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/** @file
 * @brief NIH-RPC log backend implementation.
 */

#include <zephyr/logging/log_backend.h>
#include <zephyr/logging/log_core.h>
#include <zephyr/logging/log_output.h>
#include <zephyr/logging/log_backend_std.h>
#include <zephyr/sys/__assert.h>
#include <zephyr/net/buf.h>
#include <nih_rpc.h>

#define LOG_BUFFER_SIZE 512

/* TODO: kconfig for the buf size */
static uint8_t buf[LOG_BUFFER_SIZE];

static int _out(uint8_t *data, size_t length, void *ctx)
{
	/* TODO: store global buf in ctx */
	static struct net_buf *buf = NULL;
	int err;

	ARG_UNUSED(ctx);

	if (NIH_RPC_LOG_LEVEL != 0) {
		return length;
	}

	/* if no global buf, allocate one */
	if (!buf) {
		buf = nih_rpc_alloc_buf(LOG_BUFFER_SIZE);
	}

	if (!buf) {
		return length;
	}

	(void)net_buf_add_mem(buf, data, length);

	if (length == 1 && *data != '\n') {
		/* Sending a whole line -> less overhead */
		return length;
	}

	if (!nih_rpc_is_available()) {
		/* discard lines until we are initialized */
		net_buf_unref(buf);
		goto end;
	}

	err = nih_rpc_send_log(buf);
	__ASSERT_NO_MSG(!err);
end:
	buf = NULL;

	return length;
}

LOG_OUTPUT_DEFINE(log_output_nih, _out, buf, sizeof(buf));

static bool is_uart_or_nih_rpc(uint32_t source)
{
	/* TODO: implement */
	return false;
}

static void log_backend_nih_process(const struct log_backend *const backend,
				    union log_msg_generic *msg)
{
	uint32_t source_id;
	const void *source = msg->log.hdr.source;

	if (source == NULL) {
		source_id = 0;
	} else {
		source_id = IS_ENABLED(CONFIG_LOG_RUNTIME_FILTERING) ?
		    log_dynamic_source_id((struct log_source_dynamic_data *)source) :
		    log_const_source_id((const struct log_source_const_data *)source);
	}

	/* Discard logs coming from NIH-RPC or tranport (UART driver) domain */
	if (is_uart_or_nih_rpc(source_id)) {
		return;
	}

	uint32_t flags = log_backend_std_get_flags();

	log_format_func_t log_output_func = log_format_func_t_get(LOG_OUTPUT_TEXT);

	log_output_func(&log_output_nih, &msg->log, flags);
}

static void log_backend_nih_init(struct log_backend const *const backend)
{
	/* NIH-RPC has its own auto-init mechanism */
}

static void log_backend_nih_panic(struct log_backend const *const backend)
{
	log_output_flush(&log_output_nih);
}

static void dropped(const struct log_backend *const backend, uint32_t cnt)
{
	ARG_UNUSED(backend);

	/* TODO: use log_output_dropped_process? */
	log_backend_std_dropped(&log_output_nih, cnt);
}

const struct log_backend_api log_backend_nih_api = {
	.process = log_backend_nih_process,
	.panic = log_backend_nih_panic,
	.init = log_backend_nih_init,
	.dropped = IS_ENABLED(CONFIG_LOG_MODE_IMMEDIATE) ? NULL : dropped,
};

LOG_BACKEND_DEFINE(log_backend_nih, log_backend_nih_api, true);
