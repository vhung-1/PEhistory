import pathlib
tpl = pathlib.Path("template.html").read_text(encoding="utf-8")
out = tpl
ORDER = [("__QDATA__","q_pairs.json"), ("__BTDATA__","btdata.json"),
         ("__DATA__","data.json"), ("__DPX__","daily_px.json"), ("__SWDATA__","sw_data.json")]
for tok, f in ORDER:
    assert tpl.count(tok) == 1, f"{tok} count != 1"
    out = out.replace(tok, pathlib.Path(f).read_text(encoding="utf-8").strip(), 1)
assert not any(t in out for t,_ in ORDER), "token left"
pathlib.Path("Relative_PE_Dashboard.html").write_text(out, encoding="utf-8")
print(f"built Relative_PE_Dashboard.html ({len(out)/1e6:.2f} MB)")
