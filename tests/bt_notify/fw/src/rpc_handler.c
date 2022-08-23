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

/* Those should be determined with trial and error, since they determine the
 * encoded buffer size, and because of the nature of CBOR encoding, the buffer
 * size entirely depends on the value of the elements and not their type (C
 * `sizeof` size).
 *
 * We use the small one when we only encode a simple error code, and the large
 * one when we are encoding a bunch of data (e.g. complex events).
 */
#define CBOR_BUF_SIZE_SMALL 16
#define CBOR_BUF_SIZE_LARGE 200
#define CBOR_MIN_STATES 2
/* Maximum number of CBOR elements in the payload */
#define NRF_RPC_MAX_PARAMETERS 255

#include <logging/log.h>

LOG_MODULE_REGISTER(rpc_handler, 3);

NRF_RPC_UART_TRANSPORT(test_group_tr, DEVICE_DT_GET(DT_NODELABEL(uart0)));
NRF_RPC_GROUP_DEFINE(test_group, "nrf_pytest", &test_group_tr, NULL, NULL, NULL);

/* Decode helper: expects an `err` int variable in scope. */
#define ERR_HANDLE(x)							\
	if (!err) {							\
		if (! x) {						\
			err = -EBADMSG;					\
			LOG_ERR("en/de-coding fail");			\
		} else {						\
			LOG_DBG("en/de-coding ok");}			\
	} else {							\
		LOG_ERR("failure en/de-coding previous element");	\
	};

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

void evt_ready(void)
{
	struct nrf_rpc_cbor_ctx ctx;

	NRF_RPC_CBOR_ALLOC(&test_group, ctx, CBOR_BUF_SIZE_SMALL);

	/* This event doesn't have any data. */
	nrf_rpc_cbor_evt_no_err(&test_group, RPC_EVENT_READY, &ctx);
}

void evt_nested_list(void)
{
	struct nrf_rpc_cbor_ctx ctx;
	int err = 0;

	NRF_RPC_CBOR_ALLOC(&test_group, ctx, CBOR_BUF_SIZE_LARGE);
	zcbor_state_t *zs = ctx.zs;

	ERR_HANDLE(zcbor_list_start_encode(zs, 2));

	ERR_HANDLE(zcbor_list_start_encode(zs, 2));
	ERR_HANDLE(zcbor_uint32_put(zs, 1337));
	ERR_HANDLE(zcbor_int32_put(zs, -1234));
	ERR_HANDLE(zcbor_list_end_encode(zs, 2));

	ERR_HANDLE(zcbor_list_start_encode(zs, 6));

	ERR_HANDLE(zcbor_bstr_encode_ptr(ctx.zs,
					 (const uint8_t *)"hello",
					 sizeof("hello")));
	ERR_HANDLE(zcbor_int32_put(zs, -1));
	ERR_HANDLE(zcbor_bstr_encode_ptr(ctx.zs,
					 (const uint8_t *)"from the other",
					 sizeof("from the other")));
	ERR_HANDLE(zcbor_uint32_put(zs, 2));
	ERR_HANDLE(zcbor_uint32_put(zs, 3));
	ERR_HANDLE(zcbor_bstr_encode_ptr(ctx.zs,
					 (const uint8_t *)"side",
					 sizeof("side")));

	ERR_HANDLE(zcbor_list_end_encode(zs, 6));

	ERR_HANDLE(zcbor_list_end_encode(zs, 2));

	nrf_rpc_cbor_evt_no_err(&test_group, RPC_EVENT_DEMO_NESTED_LIST, &ctx);

	LOG_INF("Sent demo event");
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
		LOG_INF("decoded addr: %s", addr_str);
	}

	/* Connection parameters */
	ERR_HANDLE(zcbor_list_start_decode(zs));

	ERR_HANDLE(decode_uint(zs, &options, sizeof(options)));
	ERR_HANDLE(decode_uint(zs, &interval, sizeof(interval)));
	ERR_HANDLE(decode_uint(zs, &window, sizeof(window)));
	ERR_HANDLE(decode_uint(zs, &timeout, sizeof(timeout)));

	if (!err) {
		LOG_INF("options %x interval %d window %d timeout %d",
			options, interval, window, timeout);
	}

	/* End conn param list */
	ERR_HANDLE(zcbor_list_end_decode(zs));

	/* End top-level list */
	ERR_HANDLE(zcbor_list_end_decode(zs));

	/* Free the RPC workqueue (and the RX buffer) */
	nrf_rpc_cbor_decoding_done(group, ctx);

	struct bt_conn *conn;

	if (!err) {
		LOG_DBG("decode ok");

		struct bt_conn_le_create_param *create_params =
			BT_CONN_LE_CREATE_PARAM(options, interval, window);

		err = bt_conn_le_create(&peer, create_params, BT_LE_CONN_PARAM_DEFAULT, &conn);
		LOG_INF("bt_conn_le_create (%d)", err);
	} else {
		LOG_ERR("%s: parsing error", __func__);
	}
}

NRF_RPC_CBOR_EVT_DECODER(test_group, test_bt_connect, RPC_ASYNC_BT_CONNECT, handler_connect, NULL);

static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR))
};

static void handler_advertise(const struct nrf_rpc_group *group,
			    struct nrf_rpc_cbor_ctx *ctx,
			    void *handler_data)
{
	LOG_DBG("");

	/* Free the RPC workqueue (and the RX buffer) */
	nrf_rpc_cbor_decoding_done(group, ctx);

	int err = bt_le_adv_start(BT_LE_ADV_CONN_NAME, ad, ARRAY_SIZE(ad), NULL, 0);
	LOG_INF("bt_le_adv_start: %d", err);

	evt_nested_list();
}

NRF_RPC_CBOR_EVT_DECODER(test_group, test_bt_advertise, RPC_ASYNC_BT_ADVERTISE, handler_advertise, NULL);

static void device_found(const bt_addr_le_t *addr,
			 int8_t rssi,
			 uint8_t type,
			 struct net_buf_simple *ad)
{
	char dev[BT_ADDR_LE_STR_LEN];

	bt_addr_le_to_str(addr, dev, sizeof(dev));
	LOG_INF("[DEVICE]: %s, AD evt type %u, AD data len %u, RSSI %i",
		dev, type, ad->len, rssi);

	if (type == BT_GAP_ADV_TYPE_ADV_IND ) {
		struct nrf_rpc_cbor_ctx ctx;
		int err = 0;
		NRF_RPC_CBOR_ALLOC(&test_group, ctx, CBOR_BUF_SIZE_LARGE);
		zcbor_state_t *zs = ctx.zs;

		/* address, type, length, rssi */
		ERR_HANDLE(zcbor_list_start_encode(zs, 4));

		/* address */
		ERR_HANDLE(zcbor_list_start_encode(zs, 2));
		ERR_HANDLE(zcbor_uint32_put(zs, addr->type));
		ERR_HANDLE(zcbor_bstr_encode_ptr(ctx.zs,
						 (const uint8_t *)(addr->a.val),
						 sizeof(addr->a.val)));
		ERR_HANDLE(zcbor_list_end_encode(zs, 2));

		ERR_HANDLE(zcbor_uint32_put(zs, type));
		ERR_HANDLE(zcbor_uint32_put(zs, ad->len));
		ERR_HANDLE(zcbor_int32_put(zs, rssi));

		ERR_HANDLE(zcbor_list_end_encode(zs, 4));

		nrf_rpc_cbor_evt_no_err(&test_group, RPC_EVENT_BT_SCAN_REPORT, &ctx);
	}
}

static void handler_scan(const struct nrf_rpc_group *group,
			 struct nrf_rpc_cbor_ctx *ctx,
			 void *handler_data)
{
	LOG_DBG("");
	uint32_t start = (uint32_t)handler_data;
	int err;

	/* Free the RPC workqueue (and the RX buffer) */
	nrf_rpc_cbor_decoding_done(group, ctx);

	if (start) {
		struct bt_le_scan_param scan_param = {
			.type       = BT_LE_SCAN_TYPE_ACTIVE,
			.options    = BT_LE_SCAN_OPT_NONE,
			.interval   = BT_GAP_SCAN_FAST_INTERVAL,
			.window     = BT_GAP_SCAN_FAST_WINDOW,
		};

		err = bt_le_scan_start(&scan_param, device_found);
		LOG_INF("bt_le_scan_start: %d", err);
	} else {
		err = bt_le_scan_stop();
		LOG_INF("bt_le_scan_stop: %d", err);
	}
}

NRF_RPC_CBOR_EVT_DECODER(test_group, test_bt_scan, RPC_ASYNC_BT_SCAN, handler_scan, (void*)1);
NRF_RPC_CBOR_EVT_DECODER(test_group, test_bt_scan_stop, RPC_ASYNC_BT_SCAN_STOP, handler_scan, (void*)0);

static void connected(struct bt_conn *conn, uint8_t conn_err)
{
	LOG_INF("connected");
	int err = 0;
	char str[BT_ADDR_LE_STR_LEN];
	const bt_addr_le_t *addr = bt_conn_get_dst(conn);

	bt_addr_le_to_str(addr, str, sizeof(str));

	if (conn_err) {
		LOG_INF("Failed to connect to %s (%u)", str, conn_err);
	} else {
		LOG_INF("Connected: %s", str);
	}

	struct nrf_rpc_cbor_ctx ctx;
	NRF_RPC_CBOR_ALLOC(&test_group, ctx, CBOR_BUF_SIZE_LARGE);
	zcbor_state_t *zs = ctx.zs;

	/* address, errcode */
	ERR_HANDLE(zcbor_list_start_encode(zs, 2));

	/* address */
	ERR_HANDLE(zcbor_list_start_encode(zs, 2));
	ERR_HANDLE(zcbor_uint32_put(zs, addr->type));
	ERR_HANDLE(zcbor_bstr_encode_ptr(ctx.zs,
					 (const uint8_t *)(addr->a.val),
					 sizeof(addr->a.val)));
	ERR_HANDLE(zcbor_list_end_encode(zs, 2));

	ERR_HANDLE(zcbor_uint32_put(zs, conn_err));

	ERR_HANDLE(zcbor_list_end_encode(zs, 2));

	nrf_rpc_cbor_evt_no_err(&test_group, RPC_EVENT_BT_CONNECTED, &ctx);

	bt_conn_unref(conn);
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
	.connected = connected,
};

/* Initialization of the UART transport, and the RPC subsystem. */
static void err_handler(const struct nrf_rpc_err_report *report)
{
	LOG_INF("nRF RPC error %d ocurred. See nRF RPC logs for more details.",
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
