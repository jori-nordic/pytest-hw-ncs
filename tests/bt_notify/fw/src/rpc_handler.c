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

void evt_ready(void)
{
	/* TODO: don't forget net_buf_reserve() inside to fit header */
	struct net_buf *buf = nih_rpc_alloc_buf(100);

	/* This event doesn't have any data. */
	nih_rpc_send_event(buf, RPC_EVENT_READY);
}

struct cmd_connect {
	bt_addr_le_t peer;
	struct bt_conn_le_create_param params;
};

static int handler_connect(struct net_buf *buf)
{
	LOG_DBG("");

	struct cmd_connect *p = net_buf_pull_mem(buf, sizeof(struct cmd_connect));

	char addr_str[BT_ADDR_LE_STR_LEN] = {0};
	bt_addr_le_to_str(&p->peer, addr_str, BT_ADDR_LE_STR_LEN);

	LOG_INF("connecting to: %s options %x interval %d window %d timeout %d", addr_str,
		p->params.options, p->params.interval, p->params.window, p->params.timeout);


	struct bt_conn *conn;

	// TODO: does this leak? conn ref
	int err = bt_conn_le_create(&p->peer, &p->params, BT_LE_CONN_PARAM_DEFAULT, &conn);
	LOG_INF("bt_conn_le_create (%d)", err);

	return err;
}

static int handler_disconnect(struct net_buf *buf)
{
	LOG_DBG("");

	return 0;
}

static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR))
};

static int handler_advertise(struct net_buf *buf)
{
	LOG_DBG("");

	int err = bt_le_adv_start(BT_LE_ADV_CONN_NAME, ad, ARRAY_SIZE(ad), NULL, 0);
	LOG_INF("bt_le_adv_start: %d", err);

	return err;
}

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

		struct net_buf *buf = nih_rpc_alloc_buf(sizeof(struct evt_device_found) + ad->len);

		struct evt_device_found *evt = (struct evt_device_found *)buf->data;

		evt->rssi = rssi;
		evt->type = type;
		bt_addr_le_copy(&evt->addr, addr);

		/* move data pointer after the struct */
		(void)net_buf_push(buf, sizeof(struct evt_device_found));

		/* copy AD */
		(void)net_buf_push_mem(buf, ad->data, ad->len);

		nih_rpc_send_event(buf, RPC_EVENT_BT_SCAN_REPORT);
	}
}

struct cmd_scan_start {
	uint8_t rssi_threshold;
};

static int handler_scan_start(struct net_buf *buf)
{
	LOG_DBG("");
	int err;
	struct cmd_scan_start *params = net_buf_pull_mem(buf, sizeof(struct cmd_scan_start));

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

	return err;
}

static int handler_scan_stop(struct net_buf *buf)
{
	LOG_DBG("");

	int err = bt_le_scan_stop();
	LOG_INF("bt_le_scan_stop: %d", err);

	return err;
}

static int handler_k_oops(struct net_buf *buf)
{
	LOG_DBG("");

	/* Trigger a panic */
	LOG_INF("Triggering panic");
	k_oops();

	return 0;
}

struct evt_connected {
	bt_addr_le_t addr;
	uint8_t conn_err;
};

static void connected(struct bt_conn *conn, uint8_t conn_err)
{
	LOG_INF("connected");

	char str[BT_ADDR_LE_STR_LEN];
	const bt_addr_le_t *addr = bt_conn_get_dst(conn);

	bt_addr_le_to_str(addr, str, sizeof(str));

	struct net_buf *buf = nih_rpc_alloc_buf(sizeof(struct evt_connected));
	struct evt_connected *evt = (struct evt_connected*)buf->data;

	if (conn_err) {
		LOG_INF("Failed to connect to %s (%u)", str, conn_err);
	} else {
		LOG_INF("Connected: %s", str);
	}

	bt_addr_le_copy(&evt->addr, addr);
	evt->conn_err = conn_err;

	(void)net_buf_push(buf, sizeof(struct evt_connected));

	nih_rpc_send_event(buf, RPC_EVENT_BT_CONNECTED);

	bt_conn_unref(conn);
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
	.connected = connected,
};

void register_handlers(void)
{
	static nih_rpc_handler_t cmd_handlers[RPC_CMD_MAX];

	cmd_handlers[RPC_CMD_BT_ADVERTISE] = handler_advertise;
	cmd_handlers[RPC_CMD_BT_SCAN] = handler_scan_start;
	cmd_handlers[RPC_CMD_BT_SCAN_STOP] = handler_scan_stop;
	cmd_handlers[RPC_CMD_BT_CONNECT] = handler_connect;
	cmd_handlers[RPC_CMD_BT_DISCONNECT] = handler_disconnect;
	cmd_handlers[RPC_CMD_K_OOPS] = handler_k_oops;
}