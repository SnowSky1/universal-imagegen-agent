# Universal ImageGen Agent

这是一个从 OpenAI Codex `imagegen` skill 改造而来的、面向通用智能体的独立项目。它把 Codex 生图能力中已经沉淀下来的任务决策流程、提示词工程、用例分类、编辑不变量和提示词范例库抽离出来，使任意具备 shell 或 Python 调用能力的智能体，都能直接复用这套成熟方法来生成和编辑图片，而不必依赖 Codex 专有的内置图片工具。

随着 Qwen-Image、Qwen-Image-2.1 等开放图像模型快速发展，智能体已经拥有越来越多可选择的生图后端。本项目不绑定某个模型：既可以连接 OpenAI Images API，也可以连接实现兼容接口的第三方服务；将 Qwen-Image 部署到本地或推理服务后，还可以通过 OpenAI-compatible 网关或新增适配器，把 Qwen 的开放模型能力与本项目继承自 Codex 的提示词库、工作流和质量约束组合起来，让不同智能体获得更稳定、更专业的生图体验。

> 当前内置的是 OpenAI-compatible Images API 适配层。Qwen 本地 Diffusers、ComfyUI 或 SGLang 推理后端尚未直接内置，需要通过兼容网关接入或新增 provider adapter。

项目提供：

- 可由任意具备 shell 能力的智能体调用的 `imagegen-agent` CLI；
- 可嵌入其他程序的 Python 接口；
- `--json` 机器可读输出和稳定的退出码；
- 独立 API 密钥、自定义 `base_url`、模型、请求头和扩展请求参数；
- 生成、编辑、多图输入、遮罩和 JSONL 批处理；
- 非覆盖式输出、dry-run、提示词结构化和敏感配置脱敏；
- 完整保留的上游技能快照，位于 `upstream/imagegen/`。

当前改造日期为 2026-09-24。新配置默认使用
`gpt-image-2.5-sunburst`，但模型不是硬编码限制，任何部署都可以通过
环境变量、TOML 或命令行替换。

## 为什么适合 Qwen-Image 等开放模型

图像模型本身决定画面生成能力，而智能体侧的任务理解、提示词组织、输入图片角色标注、编辑不变量和结果检查同样决定最终质量。这个项目负责后半部分：

- 把用户的自然语言请求转换为结构清晰、面向生产的图片提示词；
- 区分新图生成、参考图生成、局部编辑、多图合成和批量资源等任务；
- 为编辑任务持续锁定人物身份、布局、文字、边缘和背景等不变量；
- 复用 Codex `imagegen` skill 中的 use-case taxonomy 和提示词范例；
- 用统一 CLI、Python API 和 JSON 结果，让不同智能体共享同一套生图能力；
- 通过可配置 provider，将相同工作流用于 OpenAI 模型、Qwen-Image 部署或其他兼容服务。

因此，接入 Qwen-Image 并不意味着每个智能体都要重新设计提示词系统。只要部署端提供兼容 API，智能体就可以继续使用本项目的 `SKILL.md`、提示词库和执行协议；如果部署端接口不同，也只需新增 provider adapter，而不需要重写上层智能体工作流。

## 目录

```text
.
├── SKILL.md                    # 适用于通用智能体的技能说明
├── src/universal_imagegen/     # CLI、配置、提示词与 API 适配层
├── tests/                      # 不调用真实 API 的单元测试
├── references/                 # 通用提示词与集成说明
├── upstream/imagegen/          # 未修改的原始 skill 快照
├── imagegen.example.toml       # 非敏感配置示例
└── .env.example               # API 环境变量示例
```

## 安装

需要 Python 3.11 或更高版本，推荐使用 uv：

```powershell
uv sync --extra dev
```

也可以使用标准 pip：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## 配置 API

复制环境变量示例：

```powershell
Copy-Item .env.example .env
```

在本机 `.env` 中填写密钥：

```dotenv
IMAGEGEN_API_KEY=your-local-secret
IMAGEGEN_BASE_URL=https://api.openai.com/v1
IMAGEGEN_MODEL=gpt-image-2.5-sunburst
```

`.env` 已被 Git 忽略。请勿把真实密钥提交到仓库。

如需项目级非敏感配置：

```powershell
Copy-Item imagegen.example.toml .imagegen.toml
```

配置优先级从高到低为：

1. 命令行中的模型、URL、输出等非敏感参数；
2. `IMAGEGEN_*` 环境变量及 `.env`；
3. `--config`、`IMAGEGEN_CONFIG` 或当前目录 `.imagegen.toml`；
4. 项目默认值。

为了避免 shell 历史和进程列表泄密，CLI 故意不提供 `--api-key` 参数。
TOML 中只写 `api_key_env`，密钥本身放在环境变量。

### 自定义兼容服务

只要服务实现与 OpenAI Python SDK 兼容的 Images API，即可配置：

```dotenv
IMAGEGEN_API_KEY=provider-secret
IMAGEGEN_BASE_URL=https://example.com/v1
IMAGEGEN_MODEL=provider-image-model
IMAGEGEN_HEADERS_JSON={"X-Project":"demo"}
```

自定义服务会收到提示词、输入图像及请求头，请只使用可信端点。

## 常用命令

检查配置，输出会自动隐藏密钥：

```powershell
uv run imagegen-agent config
uv run imagegen-agent config --json
```

仅验证请求，不联网：

```powershell
uv run imagegen-agent generate "一只放在石桌上的陶瓷杯" `
  --use-case product-mockup `
  --style "clean product photography" `
  --constraints "no logo; no watermark" `
  --dry-run --json
```

生成：

```powershell
uv run imagegen-agent generate "A quiet alpine cabin at dawn" `
  --size 1536x1024 `
  --quality high `
  --out output/imagegen/alpine-cabin.png
```

编辑：

```powershell
uv run imagegen-agent edit `
  --image input.png `
  --prompt "Change only the background to a warm sunset" `
  --constraints "keep the subject, framing, and edges unchanged" `
  --out output/imagegen/sunset-edit.png
```

批处理：

```jsonl
{"prompt":"A gray wolf in snow","out":"wolf.png","size":"1024x1024"}
{"prompt":"A matte ceramic mug","out":"mug.png","quality":"high"}
```

```powershell
uv run imagegen-agent batch jobs.jsonl `
  --out-dir output/imagegen/batch `
  --concurrency 4 --json
```

## 智能体调用约定

智能体应优先执行 dry-run，确认提示词、模型与输出路径后再进行真实请求。
真实执行时建议使用 `--json`，其标准输出只包含结果对象，进度和错误写入
标准错误。成功退出码为 `0`，配置或输入错误为 `2`，API/网络/写入失败为
`1`。

完整的行为约束、决策树和提示词分类见 [SKILL.md](SKILL.md)。

## Python 接口

```python
from universal_imagegen import ImageGenClient, GenerateRequest, load_settings

settings = load_settings()
client = ImageGenClient(settings)
result = client.generate(
    GenerateRequest(
        prompt="A minimal ceramic mug product photo",
        out="output/imagegen/mug.png",
    )
)
print(result.outputs)
```

## 许可证和来源

项目使用 Apache License 2.0。原始 skill 未经修改保存在
`upstream/imagegen/`，改造说明见 `NOTICE`。根目录代码与文档是为通用
智能体重新组织的派生实现。
