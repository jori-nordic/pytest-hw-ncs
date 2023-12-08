/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */
#include <errno.h>
#include <zephyr/init.h>
#include <string.h>

#include <nih_rpc.h>

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/addr.h>
#include <zephyr/bluetooth/conn.h>

#include "test_rpc_opcodes.h"

// TODO: Use a buf pool depending on evt size

#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(rpc_handler, 3);

#define RPC_SIZE_SMALL 16
#define RPC_SIZE_LARGE 200

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

void evt_ready(void)
{
	/* TODO: don't forget net_buf_reserve() inside to fit header */
	struct net_buf *buf = rpc_alloc_buf(SIZE_SMALL);

	/* This event doesn't have any data. */
	rpc_send_event(buf, RPC_EVENT_READY);
}

struct cmd_connect {
	bt_addr_le_t peer;
	struct bt_le_conn_param params;
};

static void handler_connect(const struct net_buf *buf)
{
	LOG_DBG("");

	struct cmd_connect *p = net_buf_pull_mem(buf, sizeof(struct cmd_connect));

	char addr_str[BT_ADDR_LE_STR_LEN] = {0};
	bt_addr_le_to_str(p->peer, addr_str, BT_ADDR_LE_STR_LEN);

	LOG_INF("connecting to: %s options %x interval %d window %d timeout %d", addr_str,
		p->params.options, p->params.interval, p->params.window, p->params.timeout);


	struct bt_conn *conn;

	// TODO: does this leak? conn ref
	int err = bt_conn_le_create(&p->peer, &p->params, BT_LE_CONN_PARAM_DEFAULT, &conn);
	LOG_INF("bt_conn_le_create (%d)", err);
}

// NRF_RPC_CBOR_EVT_DECODER(test_group, test_bt_connect, RPC_ASYNC_BT_CONNECT, handler_connect, NULL);

static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR))
};

static void handler_advertise(const struct net_buf *buf)
{
	LOG_DBG("");

	int err = bt_le_adv_start(BT_LE_ADV_CONN_NAME, ad, ARRAY_SIZE(ad), NULL, 0);
	LOG_INF("bt_le_adv_start: %d", err);
}

// NRF_RPC_CBOR_EVT_DECODER(test_group, test_bt_advertise, RPC_ASYNC_BT_ADVERTISE, handler_advertise, NULL);

// TODO: add __packed for all wire structs

/* The event contains this + the `ad` data */
struct evt_device_found {
	bt_addr_le_t addr;
	int8_t rssi;
	uint8_t type;
	uint16_t ad_length;
};

static int8_t rssi_threshold; /* set by `handler_scan` */

static void device_found(const bt_addr_le_t *addr,
			 int8_t rssi,
			 uint8_t type,
			 struct net_buf_simple *ad)
{
	if (type == BT_GAP_ADV_TYPE_ADV_IND && rssi > rssi_threshold) {
		/* Log the device */
		char dev[BT_ADDR_LE_STR_LEN];

		bt_addr_le_to_str(addr, dev, sizeof(dev));
		LOG_INF("[DEVICE]: %s, AD evt type %u, AD data len %u, RSSI %i",
			dev, type, ad->len, rssi);

		struct net_buf *buf = rpc_alloc_buf(sizeof(struct evt_device_found) + ad->len);

		struct evt_device_found *evt = (struct evt_device_found *)buf->data;

		evt->rssi = rssi;
		evt->type = type;
		bt_le_addr_copy(&evt->addr, addr);

		/* move data pointer after the struct */
		(void)net_buf_push(buf, sizeof(struct evt_device_found));

		/* copy AD */
		(void)net_buf_push_mem(buf, ad->data, ad->len);

		rpc_send_event(buf, RPC_EVENT_BT_SCAN_REPORT);
	}
}

struct cmd_scan {
	uint8_t start;
	uint8_t rssi_threshold;
}

static void handler_scan(const struct net_buf *buf)
{
	LOG_DBG("");
	int err;
	struct cmd_scan *params = net_buf_pull_mem(sizeof(struct cmd_scan));

	if (params->start) {
		/* Store threshold for scanned devices */
		rssi_threshold = params->rssi_threshold;
		LOG_INF("RSSI threshold %d", params->rssi_threshold);

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

// NRF_RPC_CBOR_EVT_DECODER(test_group, test_bt_scan, RPC_ASYNC_BT_SCAN, handler_scan, (void*)1);
// NRF_RPC_CBOR_EVT_DECODER(test_group, test_bt_scan_stop, RPC_ASYNC_BT_SCAN_STOP, handler_scan, (void*)0);

static void handler_k_oops(const struct net_buf *buf)
{
	LOG_DBG("");

	/* Trigger a panic */
	LOG_INF("Triggering panic");
	k_oops();
}

// NRF_RPC_CBOR_EVT_DECODER(test_group, test_k_oops, RPC_ASYNC_K_OOPS, handler_k_oops, NULL);

struct evt_connected {
	bt_addr_le_t addr;
	uint8_t conn_err;
};

static void connected(struct bt_conn *conn, uint8_t conn_err)
{
	LOG_INF("connected");
	int err = 0;
	char str[BT_ADDR_LE_STR_LEN];
	const bt_addr_le_t *addr = bt_conn_get_dst(conn);

	bt_addr_le_to_str(addr, str, sizeof(str));

	struct net_buf buf = rpc_alloc_buf(sizeof(evt_connected));
	struct evt_connected *evt = (struct evt_connected)buf->data;

	if (conn_err) {
		LOG_INF("Failed to connect to %s (%u)", str, conn_err);
	} else {
		LOG_INF("Connected: %s", str);
	}

	bt_addr_le_copy(evt_connected->addr, addr);
	evt_connected = conn_err;

	(void)net_buf_push(buf, sizeof(struct evt_connected));

	rpc_send_event(buf, RPC_EVENT_BT_CONNECTED);

	bt_conn_unref(conn);
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
	.connected = connected,
};
