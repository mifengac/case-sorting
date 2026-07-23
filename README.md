# 笔录扫描件转文本（bilu-ocr）

把扫描版**打印体笔录**（PDF / 图片）转成纯文本。面向**完全离线**的内网 Ubuntu 服务器（纯 CPU，无 GPU）。

- OCR：`rapidocr_onnxruntime` + PP-OCRv5 mobile 系列 ONNX
- PDF 渲染：PyMuPDF（不需要 poppler）
- 网页：FastAPI 单页（无 CDN）
- 批处理：命令行递归目录

## 功能

1. **网页服务**：拖拽/选择上传 PDF 或图片 → 后台串行识别 → 按页展示文本 → 一键复制 / 下载 `.txt`
2. **命令行批处理**：整目录递归识别，输出同名 `.txt`
3. **阅读顺序后处理**：按坐标上→下、左→右拼行，大间距插空行分段

## 目录结构

```
bilu-ocr/
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── config.py        # 配置
│   ├── ocr_engine.py    # RapidOCR 封装 + 文本排序
│   ├── pdf_utils.py     # PDF 转图片
│   ├── tasks.py         # 串行任务队列
│   ├── batch.py         # 命令行批处理
│   ├── templates/       # 网页模板
│   └── static/          # 本地 css/js
├── models/              # 放 3 个 ONNX 模型
├── scripts/
│   ├── download_offline_bundle.sh   # 有网：打包 wheels
│   └── install_offline.sh           # 离线：装依赖
├── requirements.txt
├── run.sh
└── README.md
```

## 一、有网机器：准备离线包

```bash
cd bilu-ocr
bash scripts/download_offline_bundle.sh
```

脚本会把依赖 whl 下到 `wheels/`，并**自动下载 3 个模型**到 `models/`：

| 文件名 | 说明 | 来源（魔搭 RapidAI/RapidOCR 仓库内路径） |
|--------|------|------|
| `PP-OCRv5_mobile_det.onnx` | 检测 | `onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx` |
| `PP_OCRv4_mobile_cls.onnx` | 方向分类 | `onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx` |
| `PP-OCRv5_mobile_rec.onnx` | 识别 | `onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx` |

模型来源仓库：https://www.modelscope.cn/models/RapidAI/RapidOCR/files
（RapidOCR 官方把全部 ONNX 模型统一托管在魔搭社区；脚本下载失败时可去这里手动下载，按上表重命名。）

把项目代码 + `wheels/` + `models/*.onnx` 一并拷到内网。

## 二、离线内网：安装并启动

```bash
cd bilu-ocr
bash scripts/install_offline.sh
bash run.sh
```

浏览器打开：`http://服务器IP:8000`

### 有网快速验证（可选）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 仍需把 3 个模型放到 models/
bash run.sh
```

## 三、命令行批处理

```bash
.venv/bin/python -m app.batch /path/to/笔录目录 -o /path/to/输出目录
```

- 递归扫描 PDF 和图片
- 每个文件输出一个同名 `.txt`（替换扩展名：`张三笔录.pdf` → `张三笔录.txt`，保留相对子目录）
- 单个失败不中断，最后汇总成功/失败数

## 四、配置（环境变量）

| 变量 | 默认 | 含义 |
|------|------|------|
| `BILU_OCR_MODELS_DIR` | `./models` | 模型目录 |
| `BILU_OCR_DET_MODEL` | `models/PP-OCRv5_mobile_det.onnx` | 检测模型路径 |
| `BILU_OCR_CLS_MODEL` | `models/PP_OCRv4_mobile_cls.onnx` | 分类模型路径 |
| `BILU_OCR_REC_MODEL` | `models/PP-OCRv5_mobile_rec.onnx` | 识别模型路径 |
| `BILU_OCR_MAX_UPLOAD_MB` | `50` | 上传大小上限 |
| `BILU_OCR_MAX_PDF_PAGES` | `100` | PDF 页数上限 |
| `BILU_OCR_PDF_DPI` | `300` | PDF 渲染 DPI |
| `BILU_OCR_RESULT_TTL_HOURS` | `24` | 结果保留小时 |
| `BILU_OCR_HOST` / `BILU_OCR_PORT` | `0.0.0.0` / `8000` | 监听地址 |

## 五、限制与说明

- 单文件 ≤ 50 MB，PDF ≤ 100 页（可改环境变量）
- 识别任务**串行**排队，避免多路并发打满 CPU
- 任务状态在**内存**里，重启服务后丢失；磁盘上的上传/结果默认 24 小时清理
- 针对**打印体**笔录效果较好；手写体一般，可日后换成 server 版 ONNX 提升精度
- 页面与静态资源全部本地化，断网可用

## 六、验收建议

1. 上传一份扫描打印笔录 PDF，检查段落顺序是否可读
2. 拔网线后刷新页面，确认无外链失败
3. 用 `python -m app.batch` 跑一个混合目录
