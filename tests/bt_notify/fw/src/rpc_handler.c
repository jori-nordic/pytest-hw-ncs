/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */
#include <errno.h>
#include <zephyr/init.h>
#include <string.h>

#include <nrf_rpc/nrf_rpc_uart.h>
#include <nrf_rpc_cbor.h>

#include <zcbor_common.h>
#include <zcbor_decode.h>
#include <zcbor_encode.h>

#include <bluetooth/bluetooth.h>
#include <bluetooth/addr.h>
#include <bluetooth/conn.h>

#include "test_rpc_opcodes.h"

#define CBOR_BUF_SIZE 16

#include <logging/log.h>

LOG_MODULE_REGISTER(rpc_handler, 4);

NRF_RPC_UART_TRANSPORT(test_group_tr, DEVICE_DT_GET(DT_NODELABEL(uart0)));
NRF_RPC_GROUP_DEFINE(test_group, "nrf_sample_test", &test_group_tr, NULL, NULL, NULL);

/* Sugar, expects an `err` variable in scope. */
#define ERR_HANDLE(x) if (err || ! x) {err = -EBADMSG;}

static void errcode_rsp(int32_t err)
{
	struct nrf_rpc_cbor_ctx ctx;

	NRF_RPC_CBOR_ALLOC(&test_group, ctx, CBOR_BUF_SIZE);

	zcbor_int32_put(ctx.zs, err);

	nrf_rpc_cbor_rsp_no_err(&test_group, &ctx);
}

static bool decode_uint(struct nrf_rpc_cbor_ctx *ctx,
			void *dest,
			uint8_t bytes)
{
	uint32_t decoded;

	if (!zcbor_uint32_decode(ctx->zs, &decoded)) {
		return false;
	}

	switch (bytes) {
		case 1:
			*((uint8_t*)dest) = (uint8_t)decoded;
		case 2:
			*((uint16_t*)dest) = (uint16_t)decoded;
		case 4:
			*((uint32_t*)dest) = (uint32_t)decoded;
		default:
			return false;
	}

	return true;
}

static bool decode_addr(struct nrf_rpc_cbor_ctx *ctx,
			bt_addr_le_t *addr)
{
	int err = 0;
	struct zcbor_string zst;

	/* Address is contained in a `list` CBOR type */
	ERR_HANDLE(zcbor_list_start_decode(ctx->zs));

	ERR_HANDLE(decode_uint(ctx, &addr->type, sizeof(addr->type)));

	ERR_HANDLE(zcbor_bstr_decode(ctx->zs, &zst));

	if (!err) {
		if (ARRAY_SIZE(addr->a.val) != zst.len) {
			LOG_ERR("struct size mismatch: expect %d decoded %d",
				ARRAY_SIZE(addr->a.val), zst.len);
			return false;
		} else {
			memcpy(&addr->a.val, zst.value, zst.len);
		}
	}

	/* End of list */
	ERR_HANDLE(zcbor_list_end_decode(ctx->zs));

	if (err) {
		return false;
	} else {
		return true;
	}
}

static void handler_connect(const struct nrf_rpc_group *group,
			    struct nrf_rpc_cbor_ctx *ctx,
			    void *handler_data)
{
	LOG_DBG("");

	/* Parameters for the API call */
	bt_addr_le_t peer;
	/* struct bt_conn_le_create_param *create_param; */
	/* struct bt_le_conn_param *conn_param; */

	/* Parameters to be decoded from the RPC command data. */
	uint8_t options;
	uint16_t interval, window, timeout;


	int32_t err = 0;

	/* Decode the arguments (CBOR list) */
	ERR_HANDLE(zcbor_list_start_decode(ctx->zs));

	/* Address of the peer to connect to */
	ERR_HANDLE(decode_addr(ctx, &peer));

	/* log it */
	if (!err) {
		char addr_str[BT_ADDR_LE_STR_LEN] = {0};
		bt_addr_le_to_str(&peer, addr_str, BT_ADDR_LE_STR_LEN);
		LOG_DBG("decoded addr: %s", addr_str);
	}

	/* Connection parameters */
	ERR_HANDLE(zcbor_list_start_decode(ctx->zs));

	ERR_HANDLE(decode_uint(ctx, &options, sizeof(options)));
	ERR_HANDLE(decode_uint(ctx, &interval, sizeof(interval)));
	ERR_HANDLE(decode_uint(ctx, &window, sizeof(window)));
	ERR_HANDLE(decode_uint(ctx, &timeout, sizeof(timeout)));

	/* TODO: Place decoded items into the target structs. */
	if (!err) {
		LOG_DBG("options %x interval %d window %d timeout %d",
			options, interval, window, timeout);
	}

	/* End conn param list */
	ERR_HANDLE(zcbor_list_end_decode(ctx->zs));

	/* End top-level list */
	ERR_HANDLE(zcbor_list_end_decode(ctx->zs));

	/* Free the RPC workqueue (and the RX buffer) */
	nrf_rpc_cbor_decoding_done(group, ctx);

	if (!err) {
		LOG_DBG("decode ok");
		err = 0;
		/* err = bt_conn_le_create(&config, &addr); */
		LOG_DBG("bt_conn_le_create err %d", err);
	}

	/* Encode the errcode and send it to the other side. */
	errcode_rsp(err);
}


/* Command handlers for the test suite. Sent from python on the PC and received over UART. */
NRF_RPC_CBOR_CMD_DECODER(test_group, test_bt_connect, RPC_COMMAND_BT_CONNECT, handler_connect, NULL);
/* NRF_RPC_CBOR_CMD_DECODER(test_group, test_bt_disconnect, RPC_COMMAND_BT_DISCONNECT, handler_disconnect, NULL); */
/* NRF_RPC_CBOR_CMD_DECODER(test_group, test_bt_notify, RPC_COMMAND_BT_NOTIFY, handler_notify, NULL); */

void evt_ready(void)
{
	struct nrf_rpc_cbor_ctx ctx;

	NRF_RPC_CBOR_ALLOC(&test_group, ctx, CBOR_BUF_SIZE);

	/* This event doesn't have any data. */
	nrf_rpc_cbor_evt_no_err(&test_group, RPC_EVENT_READY, &ctx);
}

/* Initialization of the UART transport, and the RPC subsystem. */
static void err_handler(const struct nrf_rpc_err_report *report)
{
	printk("nRF RPC error %d ocurred. See nRF RPC logs for more details.",
	       report->code);
	k_oops();
}

static int rpc_init(const struct device *dev)
{
	ARG_UNUSED(dev);

	int err;

	printk("Init begin\n");

	/* It is safe to call `nrf_rpc_init` multiple times (in case there are
	 * other users of nrf-rpc on the system that also install their
	 * initializer of nrf-rpc).
	 */
	err = nrf_rpc_init(err_handler);
	if (err) {
		return -NRF_EINVAL;
	}

	printk("Init done\n");

	return 0;
}

SYS_INIT(rpc_init, POST_KERNEL, CONFIG_APPLICATION_INIT_PRIORITY);
