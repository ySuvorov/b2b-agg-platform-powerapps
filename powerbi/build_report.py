"""Generate a PBIR report (4 pages) bound to the dataverse_report semantic model
and create/update it in the B2BAgg-Analytics workspace via the Fabric REST API.

Headless replacement for the manual drag-and-drop report build.
"""
import json, uuid, sys
import fabric_lib as f

OFFER = "b2b_supplieroffer"
PROD = "b2b_canonicalproduct"       # measures live here
SUP = "b2b_supplier"

REPORT_NAME = "B2BAgg Market Intelligence"


def col(entity, prop, agg=None):
    field = {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
    if agg is not None:
        field = {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}, "Function": agg}}
        return {"field": field, "queryRef": f"{agg_name(agg)}({entity}.{prop})", "nativeQueryRef": f"{agg_name(agg)} of {prop}"}
    return {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def agg_name(a):
    return {0: "Sum", 1: "Avg", 2: "Min", 3: "Max", 5: "Count"}.get(a, "Agg")


def meas(name):
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": PROD}}, "Property": name}},
            "queryRef": f"{PROD}.{name}", "nativeQueryRef": name}


def _lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def visual(vtype, x, y, w, h, roles, z=0, title=None):
    """A data visual. If `title` is given, sets a custom container title (replacing
    the raw 'by b2b_name' auto-title). Title goes under visualContainerObjects."""
    qstate = {role: {"projections": projs} for role, projs in roles.items()}
    v = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
        "name": uuid.uuid4().hex[:20],
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": {
            "visualType": vtype,
            "query": {"queryState": qstate},
            "drillFilterOtherVisuals": True,
        },
    }
    if title:
        v["visual"]["visualContainerObjects"] = {"title": [{"properties": {
            "show": _lit("true"),
            "text": _lit(f"'{title}'"),
            "bold": _lit("true"),
        }}]}
    return [v]


def textbox(x, y, w, h, text, z=0, size=20, bold=True):
    runs = [{"value": text, "textStyle": {"fontSize": f"{size}px", "fontWeight": "bold" if bold else "normal"}}]
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
        "name": uuid.uuid4().hex[:20],
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": runs}]}}]},
            "drillFilterOtherVisuals": True,
        },
    }


# ---- Page definitions --------------------------------------------------------
PAGES = []

# Page 1 — Regional Demand
p1 = {
    "name": "regional_demand",
    "display": "Regional Demand",
    "visuals": [
        textbox(16, 12, 700, 40, "Regional Demand & Stock"),
        visual("clusteredBarChart", 16, 60, 620, 400, {
            "Category": [col(OFFER, "b2b_warehouse_city")],
            "Y": [meas("Total Stock")],
        }, z=1, title="Total Stock by City"),
        visual("card", 650, 60, 200, 120, {"Values": [meas("Total Stock")]}, z=2),
        visual("card", 860, 60, 200, 120, {"Values": [meas("Distinct SKU Count")]}, z=3),
        visual("card", 1070, 60, 190, 120, {"Values": [meas("Offer Count")]}, z=4),
        visual("tableEx", 650, 190, 610, 270, {"Values": [
            col(OFFER, "b2b_warehouse_city"), meas("Total Stock"),
            meas("Distinct SKU Count"), meas("Avg Lead Days")]}, z=5),
        visual("slicer", 16, 470, 300, 230, {"Values": [col(PROD, "b2b_brand")]}, z=6),
        visual("slicer", 330, 470, 300, 230, {"Values": [col(PROD, "b2b_seasonname")]}, z=7),
    ],
}

# Page 2 — Supplier Scorecard
p2 = {
    "name": "supplier_scorecard",
    "display": "Supplier Scorecard",
    "visuals": [
        textbox(16, 12, 700, 40, "Supplier Scorecard"),
        visual("tableEx", 16, 60, 760, 320, {"Values": [
            col(SUP, "b2b_name"), meas("Offer Count"), meas("Fill Rate %"),
            meas("Price Competitiveness %"), meas("Supplier Stock Rank")]}, z=1),
        visual("clusteredBarChart", 790, 60, 470, 320, {
            "Category": [col(SUP, "b2b_name")],
            "Y": [meas("Total Stock")],
        }, z=2, title="Total Stock by Supplier"),
        visual("card", 16, 390, 240, 120, {"Values": [meas("Inventory Value")]}, z=3),
        visual("slicer", 270, 390, 250, 230, {"Values": [col(PROD, "b2b_brand")]}, z=4),
        visual("slicer", 530, 390, 250, 230, {"Values": [col(PROD, "b2b_seasonname")]}, z=5),
    ],
}

# Page 3 — Top-moving SKUs
p3 = {
    "name": "top_moving_skus",
    "display": "Top-Moving SKUs",
    "visuals": [
        textbox(16, 12, 700, 40, "Top-Moving SKUs"),
        visual("clusteredBarChart", 16, 60, 620, 440, {
            "Category": [col(PROD, "b2b_name")],
            "Y": [meas("Total Stock")],
            "Series": [col(PROD, "b2b_brand")],
        }, z=1, title="Stock by Product (legend = Brand)"),
        visual("tableEx", 650, 60, 610, 320, {"Values": [
            col(OFFER, "b2b_raw_sku"), col(OFFER, "b2b_suppliername"),
            col(OFFER, "b2b_price", agg=2), meas("Supplier Count per SKU")]}, z=2),
        visual("card", 650, 390, 240, 110, {"Values": [meas("Inventory Value")]}, z=3),
        visual("slicer", 910, 390, 350, 110, {"Values": [col(PROD, "b2b_diameter")]}, z=4),
    ],
}

# Page 4 — Price Spread & Competitiveness
p4 = {
    "name": "price_spread",
    "display": "Price Spread",
    "visuals": [
        textbox(16, 12, 700, 40, "Price Spread & Competitiveness"),
        visual("clusteredColumnChart", 16, 60, 760, 400, {
            "Category": [col(PROD, "b2b_name")],
            "Y": [meas("Min Price this Season"), col(OFFER, "b2b_price", agg=1), meas("Price Spread")],
        }, z=1, title="Min / Avg / Spread by Product"),
        visual("card", 790, 60, 230, 120, {"Values": [meas("Summer vs Winter Price Ratio")]}, z=2),
        visual("card", 1030, 60, 230, 120, {"Values": [meas("Brand Price Premium")]}, z=3),
        visual("card", 790, 190, 230, 120, {"Values": [meas("Avg Summer Price")]}, z=4),
        visual("card", 1030, 190, 230, 120, {"Values": [meas("Avg Winter Price")]}, z=5),
        visual("slicer", 790, 320, 230, 140, {"Values": [col(PROD, "b2b_seasonname")]}, z=6),
        visual("slicer", 1030, 320, 230, 140, {"Values": [col(PROD, "b2b_brand")]}, z=7),
    ],
}

PAGES = [p1, p2, p3, p4]


def build_parts():
    parts = []

    def add(path, obj):
        parts.append({"path": path, "payload": f.b64(json.dumps(obj)), "payloadType": "InlineBase64"})

    # definition.pbir — connection to the semantic model (REST: byConnection connectionString)
    pbir = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {
            "byConnection": {
                "connectionString": f"semanticmodelid={f.MODEL_ID}",
            },
        },
    }
    add("definition.pbir", pbir)

    # version.json — required for PBIR format
    add("definition/version.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })

    # report.json
    report = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/2.0.0/schema.json",
        "themeCollection": {"baseTheme": {
            "name": "CY24SU10",
            "reportVersionAtImport": "5.55",
            "type": "SharedResources",
        }},
        "settings": {"useStylableVisualContainerHeader": True},
    }
    add("definition/report.json", report)

    # pages.json
    pages_meta = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p["name"] for p in PAGES],
        "activePageName": PAGES[0]["name"],
    }
    add("definition/pages/pages.json", pages_meta)

    for p in PAGES:
        page = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.0.0/schema.json",
            "name": p["name"],
            "displayName": p["display"],
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        }
        add(f"definition/pages/{p['name']}/page.json", page)
        # p["visuals"] may contain dicts (textbox/single visual) or lists (label+visual)
        flat = []
        for item in p["visuals"]:
            flat.extend(item if isinstance(item, list) else [item])
        for v in flat:
            add(f"definition/pages/{p['name']}/visuals/{v['name']}/visual.json", v)

    return parts


def main():
    tok = f.token()
    parts = build_parts()
    print(f"Built {len(parts)} parts")

    # find existing report
    items = f.call("GET", f"https://api.fabric.microsoft.com/v1/workspaces/{f.WS}/reports", tok)
    existing = None
    for it in items.get("value", []):
        if it.get("displayName") == REPORT_NAME:
            existing = it["id"]

    definition = {"parts": parts}
    if existing:
        print("Updating existing report", existing)
        body = {"definition": definition}
        r = f.call("POST", f"https://api.fabric.microsoft.com/v1/workspaces/{f.WS}/reports/{existing}/updateDefinition", tok, body=body)
    else:
        print("Creating new report")
        body = {"displayName": REPORT_NAME, "definition": definition}
        r = f.call("POST", f"https://api.fabric.microsoft.com/v1/workspaces/{f.WS}/reports", tok, body=body)
    print("Result:", json.dumps(r)[:400])


if __name__ == "__main__":
    main()
