/*!
 * Copyright (C) Microsoft Corporation. All rights reserved.
 * This file is auto-generated. Do not modify it manually.
 * Changes to this file may be overwritten.
 */

export const dataSourcesInfo = {
  "b2b_canonicalproducts": {
    "tableId": "",
    "version": "",
    "primaryKey": "b2b_canonicalproductid",
    "dataSourceType": "Dataverse",
    "apis": {}
  },
  "b2b_orderlines": {
    "tableId": "",
    "version": "",
    "primaryKey": "b2b_orderlineid",
    "dataSourceType": "Dataverse",
    "apis": {}
  },
  "b2b_orders": {
    "tableId": "",
    "version": "",
    "primaryKey": "b2b_orderid",
    "dataSourceType": "Dataverse",
    "apis": {}
  },
  "b2b_regions": {
    "tableId": "",
    "version": "",
    "primaryKey": "b2b_regionid",
    "dataSourceType": "Dataverse",
    "apis": {}
  },
  "b2b_supplieroffers": {
    "tableId": "",
    "version": "",
    "primaryKey": "b2b_supplierofferid",
    "dataSourceType": "Dataverse",
    "apis": {}
  },
  "b2b_suppliers": {
    "tableId": "",
    "version": "",
    "primaryKey": "b2b_supplierid",
    "dataSourceType": "Dataverse",
    "apis": {}
  },
  "b2b_warehouses": {
    "tableId": "",
    "version": "",
    "primaryKey": "b2b_warehouseid",
    "dataSourceType": "Dataverse",
    "apis": {}
  },
  "rfqbroadcast": {
    "tableId": "",
    "version": "",
    "primaryKey": "",
    "dataSourceType": "Connector",
    "apis": {
      "Run": {
        "path": "/{connectionId}/triggers/manual/run",
        "method": "POST",
        "parameters": [
          {
            "name": "connectionId",
            "in": "path",
            "required": true,
            "type": "string"
          },
          {
            "name": "input",
            "in": "body",
            "required": true,
            "type": "object"
          },
          {
            "name": "api-version",
            "in": "query",
            "required": true,
            "type": "string"
          }
        ],
        "responseInfo": {
          "200": {
            "type": "object"
          },
          "default": {
            "type": "object"
          }
        }
      }
    }
  }
};
