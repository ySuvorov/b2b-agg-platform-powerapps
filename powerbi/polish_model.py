"""Safe polish pass on the dataverse_report semantic model:
  - sets sensible formatStrings on % / currency / ratio measures
  - fixes 'Supplier Stock Rank' to rank over the supplier dimension the visual uses
No column renames, no DAX logic changes beyond the rank's ALL() target.
"""
import re, json
import fabric_lib as f

TABLE_PART = "definition/tables/b2b_canonicalproduct.tmdl"

FORMATS = {
    "Fill Rate %": '0.0"%"',
    "Price Competitiveness %": '0.0"%"',
    "Region Stock Share %": '0.0"%"',
    "Inventory Value": '\\$#,##0',
    "Avg Summer Price": '\\$#,##0.00',
    "Avg Winter Price": '\\$#,##0.00',
    "Brand Price Premium": '\\$#,##0.00',
    "Min Price this Season": '\\$#,##0.00',
    "Price Spread": '\\$#,##0.00',
    "Summer vs Winter Price Ratio": "0.00",
    "Avg Lead Days": "0.00",
}

MEAS_RE = re.compile(r"^\tmeasure\s+(?:'([^']+)'|(\S+))\s*=")


def polish(text: str) -> str:
    lines = text.split("\n")
    out = []
    cur = None
    emitted = set()  # measures whose formatString we've placed
    i = 0
    while i < len(lines):
        line = lines[i]
        m = MEAS_RE.match(line)
        if m:
            cur = m.group(1) or m.group(2)

        # fix the rank measure's ALL() target (scoped to current measure)
        if cur == "Supplier Stock Rank" and "ALL(b2b_supplieroffer[b2b_suppliername])" in line:
            line = line.replace("ALL(b2b_supplieroffer[b2b_suppliername])",
                                "ALL(b2b_supplier[b2b_name])")

        # drop PBI_FormatHint annotation for measures we're reformatting
        if cur in FORMATS and line.strip().startswith("annotation PBI_FormatHint"):
            # also swallow a following blank line if present
            if i + 1 < len(lines) and lines[i + 1].strip() == "":
                i += 1
            i += 1
            continue

        # replace an existing formatString line for a target measure
        if cur in FORMATS and line.strip().startswith("formatString:"):
            out.append(f"\t\tformatString: {FORMATS[cur]}")
            emitted.add(cur)
            i += 1
            continue

        # insert formatString before lineageTag if not yet emitted
        if cur in FORMATS and cur not in emitted and line.strip().startswith("lineageTag:"):
            out.append(f"\t\tformatString: {FORMATS[cur]}")
            emitted.add(cur)

        out.append(line)
        i += 1
    return "\n".join(out)


def main():
    tok = f.token()
    d = f.call("POST", f"https://api.fabric.microsoft.com/v1/workspaces/{f.WS}/semanticModels/{f.MODEL_ID}/getDefinition", tok, body={})
    parts = d["definition"]["parts"]
    new_parts = []
    changed = False
    for p in parts:
        if p["path"] == TABLE_PART:
            txt = f.unb64(p["payload"])
            newtxt = polish(txt)
            if newtxt != txt:
                changed = True
                # quick sanity print
                print("rank fix:", "ALL(b2b_supplier[b2b_name])" in newtxt)
                for name in FORMATS:
                    assert f"measure '{name}'" in newtxt, f"lost measure {name}"
                p = {"path": p["path"], "payload": f.b64(newtxt), "payloadType": "InlineBase64"}
        new_parts.append({"path": p["path"], "payload": p["payload"], "payloadType": "InlineBase64"})
    if not changed:
        print("no change")
        return
    body = {"definition": {"parts": new_parts}}
    r = f.call("POST", f"https://api.fabric.microsoft.com/v1/workspaces/{f.WS}/semanticModels/{f.MODEL_ID}/updateDefinition", tok, body=body)
    print("updateDefinition:", json.dumps(r)[:300])


if __name__ == "__main__":
    main()
