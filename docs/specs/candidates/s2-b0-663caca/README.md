# 未接受的 S2 候選來源封存

此封存只供 B0 對照重播及後續逐刀移植，不會加入 `tools/` imports 或測試 discovery。候選不是已接受的 S2 實作；凍結規格仍是唯一行為依據。

`selected-source.zip` 保存候選 commit `663caca91a7eb06b10a7c1e5a27f10caf97ad9b7` 的 12 個選定 Git blobs：五個 S2 模組、五份測試、Product Manifest schema，以及它們使用的 shared resolver。`source-manifest.json` 保存每檔 Git blob ID、SHA-256 與整份 ZIP 指紋。未包含公司文件、舊 S2-A、治理、hook 或 memory 變更。

重播方式：在獨立暫存目錄匯出已公開的 baseline `a5a32163e153b247e5714399ce3d615f70937229`，使用 `git -c core.autocrlf=false archive --format=zip` 保留 Git bytes；核對封存 SHA-256 與 12 個 member 的 SHA-256，再將封存解開覆蓋該暫存副本。不要覆蓋任何工作目錄。

在暫存副本執行：

```powershell
python -X utf8 -m unittest discover -s tests -p 'test_implementation_*.py' -v
python -X utf8 -m unittest discover -s tests -p 'test_product_*.py' -v
```

本次封存重播共 65 run / 64 pass / 1 Windows OS symlink privilege skip，與原候選診斷相同。封存 member bytes 逐檔比對原 Git blobs 一致。PASS 仍不消除 B0 已記錄的錯誤 oracle 與 admission/item 缺口。
