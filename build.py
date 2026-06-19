import pathlib
tpl  = pathlib.Path("template.html").read_text(encoding="utf-8")
qd   = pathlib.Path("q_pairs.json").read_text(encoding="utf-8").strip()
bt   = pathlib.Path("btdata.json").read_text(encoding="utf-8").strip()
data = pathlib.Path("data.json").read_text(encoding="utf-8").strip()
dpx  = pathlib.Path("daily_px.json").read_text(encoding="utf-8").strip()
for tok in ("__QDATA__","__BTDATA__","__DATA__","__DPX__"):
    assert tpl.count(tok) == 1, f"{tok} count != 1"
out = (tpl.replace("__QDATA__", qd, 1)
          .replace("__BTDATA__", bt, 1)
          .replace("__DATA__", data, 1)
          .replace("__DPX__", dpx, 1))
assert not any(t in out for t in ("__QDATA__","__BTDATA__","__DATA__","__DPX__")), "token left"
pathlib.Path("Relative_PE_Dashboard.html").write_text(out, encoding="utf-8")
print(f"built Relative_PE_Dashboard.html ({len(out)/1e6:.2f} MB)")
