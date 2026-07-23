# OCR 模型文件

本目录需要放置 **3 个 ONNX 模型**（启动时本地加载，**禁止联网下载**）：

| 文件名 | 作用 | 大约体积 |
|--------|------|----------|
| `PP-OCRv5_mobile_det.onnx` | 文字检测（找出字在哪） | ~5 MB |
| `PP_OCRv4_mobile_cls.onnx` | 方向分类（是否倒置） | ~1.5 MB |
| `PP-OCRv5_mobile_rec.onnx` | 文字识别（读出内容） | ~16 MB |

## 去哪里下载

最简单：在有网机器上运行 `scripts/download_offline_bundle.sh`，会自动下载并按上表重命名。

手动下载的话，到魔搭社区 RapidOCR 官方模型仓库（全部模型统一托管在此）：

- 仓库：https://www.modelscope.cn/models/RapidAI/RapidOCR/files
- `onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx` → 重命名为 `PP-OCRv5_mobile_det.onnx`
- `onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx` → 重命名为 `PP_OCRv4_mobile_cls.onnx`
- `onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx` → 重命名为 `PP-OCRv5_mobile_rec.onnx`

也可用环境变量指定任意路径（不必放在本目录）：

```bash
export BILU_OCR_DET_MODEL=/path/to/det.onnx
export BILU_OCR_CLS_MODEL=/path/to/cls.onnx
export BILU_OCR_REC_MODEL=/path/to/rec.onnx
```

## 说明

- 方向分类模型仍用 PP-OCRv4 的 cls，与官方 RapidOCR 常见组合一致。
- 若以后要提升精度，可把 det/rec 换成 server 版 ONNX，只需替换文件或改环境变量，代码不用动。
