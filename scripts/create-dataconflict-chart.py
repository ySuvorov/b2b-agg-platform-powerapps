#!/usr/bin/env python3
"""
create-dataconflict-chart.py — create the native system chart "Conflicts by
Status" on b2b_dataconflict (Option B for the MVP2 demo: the native Kanban
control is hard-locked to Opportunity/Activity tables only, so we visualise the
review queue with a grouped view + this column chart instead).

The chart counts conflict rows grouped by b2b_status (Pending / NeedsReview /
NewCandidate / Approved / Rejected / AutoResolved). Fully scriptable via the
savedqueryvisualization Web API entity — no portal step.

Idempotent: matched by (name, primaryentitytypecode). Re-run updates in place.

Auth: az account get-access-token (QUIRK #1).
  az login   # <admin-upn>
  python3 scripts/create-dataconflict-chart.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

DV = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DV}/api/data/v9.2"
ENTITY = "b2b_dataconflict"
CHART_NAME = "Conflicts by Status"

DATA_DESCRIPTION = """<datadefinition>
  <fetchcollection>
    <fetch aggregate="true" mapping="logical">
      <entity name="b2b_dataconflict">
        <attribute name="b2b_dataconflictid" aggregate="countcolumn" alias="count_col" />
        <attribute name="b2b_status" groupby="true" alias="groupby_status" />
        <order alias="groupby_status" descending="false" />
      </entity>
    </fetch>
  </fetchcollection>
  <categorycollection>
    <category>
      <measurecollection>
        <measure alias="count_col" />
      </measurecollection>
    </category>
  </categorycollection>
</datadefinition>"""

PRESENTATION_DESCRIPTION = """<Chart Palette="BrightPastel" PaletteCustomColors="">
  <Series>
    <Series IsValueShownAsLabel="true" Color="59, 70, 130" ChartType="Column" Font="{0}, 9.5px" LabelForeColor="59, 59, 59">
      <SmartLabelStyle Enabled="True" />
      <Points />
    </Series>
  </Series>
  <ChartAreas>
    <ChartArea BorderColor="White" BorderDashStyle="Solid">
      <AxisY LabelAutoFitMinFontSize="8" TitleForeColor="59, 59, 59">
        <MajorGrid LineColor="239, 242, 246" />
        <LabelStyle Font="{0}, 10.5px" ForeColor="59, 59, 59" />
      </AxisY>
      <AxisX LabelAutoFitMinFontSize="8" TitleForeColor="59, 59, 59">
        <MajorGrid LineColor="239, 242, 246" />
        <LabelStyle Font="{0}, 10.5px" ForeColor="59, 59, 59" />
      </AxisX>
    </ChartArea>
  </ChartAreas>
  <Legends>
    <Legend Alignment="Center" LegendStyle="Table" Docking="Bottom" IsEquallySpacedItems="True" Font="{0}, 11px" ShadowColor="0, 0, 0, 0" ForeColor="59, 59, 59" />
  </Legends>
  <Titles>
    <Title Alignment="TopLeft" DockingOffset="-3" Font="{0}, 13px, style=Bold" ForeColor="34, 40, 72" />
  </Titles>
</Chart>"""


def token() -> str:
    out = subprocess.run(
        ["az", "account", "get-access-token", "--resource", DV,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True,
    )
    tok = out.stdout.strip()
    if not tok:
        sys.exit(f"No az token. Run `az login`.\n{out.stderr}")
    return tok


def _req(method: str, path: str, tok: str, body: dict | None = None,
         prefer: str | None = None):
    url = f"{API}/{path}"
    if "?" in url:
        base, q = url.split("?", 1)
        url = base + "?" + urllib.parse.quote(q, safe="=&$,'()/")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Accept", "application/json")
    req.add_header("OData-MaxVersion", "4.0")
    req.add_header("OData-Version", "4.0")
    if prefer:
        req.add_header("Prefer", prefer)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return (json.loads(raw) if raw else {}), r.status, r.headers
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code}\n{e.read().decode()[:800]}")


def main() -> None:
    tok = token()
    payload = {
        "name": CHART_NAME,
        "description": "Review queue distribution across statuses (Pending / NeedsReview / NewCandidate / Approved / Rejected / AutoResolved). Demo visual for the SKU Resolution Engine conflict queue.",
        "primaryentitytypecode": ENTITY,
        "datadescription": DATA_DESCRIPTION,
        "presentationdescription": PRESENTATION_DESCRIPTION,
        "isdefault": False,
    }

    existing, _, _ = _req(
        "GET",
        f"savedqueryvisualizations?$select=savedqueryvisualizationid&"
        f"$filter=name eq '{CHART_NAME}' and primaryentitytypecode eq '{ENTITY}'",
        tok)
    rows = existing.get("value", [])
    if rows:
        vid = rows[0]["savedqueryvisualizationid"]
        _req("PATCH", f"savedqueryvisualizations({vid})", tok, payload)
        print(f"  ~ updated chart '{CHART_NAME}' ({vid})")
    else:
        _, _, hdrs = _req("POST", "savedqueryvisualizations", tok, payload,
                          prefer="return=representation")
        loc = hdrs.get("OData-EntityId", "")
        print(f"  + created chart '{CHART_NAME}' {loc}")

    _req("POST", "PublishXml", tok,
         {"ParameterXml": f"<importexportxml><entities><entity>{ENTITY}</entity></entities></importexportxml>"})
    print("  published.")
    print(f"\nDone. In the app's Data Conflicts view, the chart pane -> '{CHART_NAME}'.")


if __name__ == "__main__":
    main()
