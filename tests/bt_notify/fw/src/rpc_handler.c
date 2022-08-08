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
#define CBOR_MIN_STATES 2
/* Maximum number of CBOR elements in the payload */
#define NRF_RPC_MAX_PARAMETERS 255

#include <logging/log.h>

LOG_MODULE_REGISTER(rpc_handler, 4);

NRF_RPC_UART_TRANSPORT(test_group_tr, DEVICE_DT_GET(DT_NODELABEL(uart0)));
NRF_RPC_GROUP_DEFINE(test_group, "nrf_pytest", &test_group_tr, NULL, NULL, NULL);

/* Decode helper: expects an `err` int variable in scope. */
#define ERR_HANDLE(x)							\
	if (!err) {							\
		if (! x) {						\
			err = -EBADMSG;					\
			LOG_ERR("decoding failed");			\
		} else {						\
			LOG_DBG("decoding ok");}			\
	} else {							\
		LOG_DBG("failure decoding previous element");		\
	};

static void errcode_rsp(int32_t err)
{
	struct nrf_rpc_cbor_ctx ctx;

	NRF_RPC_CBOR_ALLOC(&test_group, ctx, CBOR_BUF_SIZE);

	zcbor_int32_put(ctx.zs, err);

	nrf_rpc_cbor_rsp_no_err(&test_group, &ctx);
}

static bool decode_uint(zcbor_state_t *zs,
			void *dest,
			uint8_t bytes)
{
	uint32_t decoded;

	if (!zcbor_uint32_decode(zs, &decoded)) {
		return false;
	}

	switch (bytes) {
		case 1:
			*((uint8_t*)dest) = (uint8_t)decoded;
			break;
		case 2:
			*((uint16_t*)dest) = (uint16_t)decoded;
			break;
		case 4:
			*((uint32_t*)dest) = (uint32_t)decoded;
			break;
		default:
			return false;
	}

	return true;
}

static bool decode_addr(zcbor_state_t *zs,
			bt_addr_le_t *addr)
{
	int err = 0;
	struct zcbor_string zst;
	LOG_DBG("");

	/* Address is contained in a `list` CBOR type */
	ERR_HANDLE(zcbor_list_start_decode(zs));

	ERR_HANDLE(decode_uint(zs, &addr->type, sizeof(addr->type)));

	ERR_HANDLE(zcbor_bstr_decode(zs, &zst));

	if (!err) {
		if (ARRAY_SIZE(addr->a.val) != zst.len) {
			LOG_ERR("struct size mismatch: expect %d decoded %d",
				ARRAY_SIZE(addr->a.val), zst.len);
			LOG_DBG("exit");
			return false;
		} else {
			memcpy(&addr->a.val, zst.value, zst.len);
		}
	}

	/* End of list */
	ERR_HANDLE(zcbor_list_end_decode(zs));

	LOG_DBG("exit");
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

	size_t payload_len = ctx->zs->payload_end - ctx->zs->payload;

	/* We need one additional ZCBOR state per list depth: we will not use
	 * the one supplied by nrf-rpc, but rather allocate a new one to parse
	 * the payload (2 list levels).
	 */
	zcbor_state_t zs[CBOR_MIN_STATES + 2];
	zcbor_new_decode_state(zs, ARRAY_SIZE(zs),
			       ctx->out_packet, payload_len,
			       NRF_RPC_MAX_PARAMETERS);

	/* Parameters for the API call */
	bt_addr_le_t peer;

	/* Parameters to be decoded from the RPC command data. */
	uint8_t options;
	uint16_t interval, window, timeout;

	int32_t err = 0;

	/* Decode the arguments (CBOR list) */
	ERR_HANDLE(zcbor_list_start_decode(zs));

	/* Address of the peer to connect to */
	ERR_HANDLE(decode_addr(zs, &peer));

	/* log it */
	if (!err) {
		char addr_str[BT_ADDR_LE_STR_LEN] = {0};
		bt_addr_le_to_str(&peer, addr_str, BT_ADDR_LE_STR_LEN);
		LOG_DBG("decoded addr: %s", addr_str);
	}

	/* Connection parameters */
	ERR_HANDLE(zcbor_list_start_decode(zs));

	ERR_HANDLE(decode_uint(zs, &options, sizeof(options)));
	ERR_HANDLE(decode_uint(zs, &interval, sizeof(interval)));
	ERR_HANDLE(decode_uint(zs, &window, sizeof(window)));
	ERR_HANDLE(decode_uint(zs, &timeout, sizeof(timeout)));

	if (!err) {
		LOG_DBG("options %x interval %d window %d timeout %d",
			options, interval, window, timeout);
	}

	/* End conn param list */
	ERR_HANDLE(zcbor_list_end_decode(zs));

	/* End top-level list */
	ERR_HANDLE(zcbor_list_end_decode(zs));

	/* Free the RPC workqueue (and the RX buffer) */
	nrf_rpc_cbor_decoding_done(group, ctx);

	if (!err) {
		LOG_DBG("decode ok");
		err = 0;
		/* Place decoded items into the target structs, and call
		 * `bt_conn_le_create`.
		 */
		LOG_DBG("bt_conn_le_create (%d)", err);
	} else {
		LOG_ERR("%s: parsing error", __func__);
	}

	/* Encode the errcode and send it to the other side. */
	errcode_rsp(err);
}

static void handler_advertise(const struct nrf_rpc_group *group,
			    struct nrf_rpc_cbor_ctx *ctx,
			    void *handler_data)
{
	LOG_DBG("");

	/* Free the RPC workqueue (and the RX buffer) */
	nrf_rpc_cbor_decoding_done(group, ctx);

	LOG_DBG("start advertising");

	/* Encode the errcode and send it to the other side. */
	errcode_rsp(0);
}


/* Command handlers for the test suite. Sent from python on the PC and received over UART. */
NRF_RPC_CBOR_CMD_DECODER(test_group, test_bt_advertise, RPC_COMMAND_BT_ADVERTISE, handler_advertise, NULL);
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

	LOG_DBG("Init begin");

	/* It is safe to call `nrf_rpc_init` multiple times (in case there are
	 * other users of nrf-rpc on the system that also install their
	 * initializer of nrf-rpc).
	 */
	err = nrf_rpc_init(err_handler);
	if (err) {
		return -NRF_EINVAL;
	}

	LOG_DBG("Init done");

	return 0;
}

SYS_INIT(rpc_init, POST_KERNEL, CONFIG_APPLICATION_INIT_PRIORITY);
