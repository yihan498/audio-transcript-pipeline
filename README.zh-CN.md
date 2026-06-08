# 音频转文字工作流

语言：中文 | [English README](README.en.md)

## 版本说明 v01

2026-06-08 v01：新增中文工作流说明，完整描述音频转文字链路、环境配置、烟测、批量转录、断点续跑、最终收集、输出校验和隐私边界；不展示任何具体音频内容或转录内容。

## 这是什么

这是一个可复用的音频转文字工作流，适用于课程音频、直播回放音频、访谈录音等本地音频文件。它默认使用中国国内模型服务，核心目标是把“拿到音频”到“产出可阅读文字稿”的链路拆清楚。

工作流会把不同层级的产物分开：

- 来源清单
- 原始 ASR 文字稿
- 可选的清理稿
- 可选的阅读笔记或复核稿
- 最终集中导出的文字稿文件夹

这套流程把转录当作证据链处理：先确认原始音频是否可用，再生成原始文字稿；只有原始文字稿存在后，才进入清理、整理、笔记或总结阶段。

## 隐私边界

公开工作流包中不要包含：

- 原始音频文件
- 生成的真实文字稿
- 分块缓存
- 运行日志
- API Key
- 浏览器登录状态或认证缓存

可保留在公开包中的内容：

- 流程文档
- 脚本
- 不含真实内容的示例
- 参考规则和接口约定
- `.gitignore`

真实任务产物默认放在本地 `jobs/` 中，除非你明确制作了脱敏样例，否则不应放入公开仓库。

## 默认模型路线

默认路线：

- ASR：阿里云百炼 DashScope 短音频 ASR，常用模型为 `qwen3-asr-flash`
- 长音频：先把本地 MP3 按 API 限制切成小块，再逐块转录，最后合并成每讲一份文字稿
- 清理：在原始文字稿生成后，再用 Qwen 或 DeepSeek 做标点、分段和可读性清理
- 笔记或复核：使用 DeepSeek 或 Qwen，作为单独的加工层保存

备用路线：

- 如果公开 URL 或签名媒体 URL 无法被 ASR 服务访问，改用本地音频文件。
- 如果某次 API 调用因为网络断连失败，使用同一个输出目录重新运行批处理命令；已完成的分块和课程会自动跳过。
- 如果遇到欠费或额度不足，充值或切换服务后，用同一个任务目录继续运行。

## 目录结构

```text
standalone-skill-xiaoe-audio-transcript-pipeline-v01/
  README.md
  README.zh-CN.md
  README.en.md
  SKILL.md
  .gitignore
  references/
    engine-contract.md
    cleanup-rules.md
    output-conventions.md
  scripts/
    audio_transcript_pipeline.py
    dashscope_smoke_test.py
    dashscope_asr_smoke_test.py
    deepseek_smoke_test.py
    run_short_audio_pipeline.py
    deepseek_notes_from_cleaned.py
    dashscope_url_transcribe.py
    mp3_frame_splitter.py
    transcribe_local_mp3_batch.py
    collect_transcripts.py
  examples/
  jobs/                  # 本地生成产物
```

## 环境配置

建议使用 Python 3.10 或更新版本。

在 Windows PowerShell 中设置 API Key：

```powershell
setx DASHSCOPE_API_KEY "your_dashscope_key"
setx DEEPSEEK_API_KEY "your_deepseek_key"
```

`setx` 会把变量写入 Windows 用户环境，但不会立即更新当前 PowerShell 进程。当前窗口中需要再执行：

```powershell
$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')
```

检查 Key 是否可见：

```powershell
python -c "import os; print(bool(os.getenv('DASHSCOPE_API_KEY')))"
python -c "import os; print(bool(os.getenv('DEEPSEEK_API_KEY')))"
```

## 烟测

测试 DashScope 文本访问：

```powershell
python scripts\dashscope_smoke_test.py --model qwen-plus
```

用一个小音频测试 DashScope 短音频 ASR：

```powershell
python scripts\dashscope_asr_smoke_test.py --audio "D:\path\to\short-sample.mp3" --model qwen3-asr-flash
```

测试 DeepSeek 文本访问：

```powershell
python scripts\deepseek_smoke_test.py --model deepseek-v4-flash
```

只有这些烟测通过后，再开始大批量转录。

## 批量转录流程

创建一个带版本号的任务目录：

```powershell
$jobRoot = "D:\path\to\jobs\part-transcript-YYYYMMDD-v01"
New-Item -ItemType Directory -Force -Path $jobRoot | Out-Null
```

运行本地 MP3 批量转录：

```powershell
python scripts\transcribe_local_mp3_batch.py `
  --input-dir "D:\path\to\audio-folder" `
  --out-root "$jobRoot" `
  --model qwen3-asr-flash
```

常用可选参数：

```powershell
--max-seconds 240
--max-bytes 9500000
--retries 3
--limit 3
--start-at "filename fragment"
```

批处理脚本会执行以下步骤：

1. 从 `--input-dir` 读取本地 MP3 文件。
2. 在 `--out-root` 下为每个音频创建单独任务目录。
3. 按 MP3 帧边界切分为符合 API 限制的小块。
4. 将每个音频块发送给 DashScope 短音频 ASR。
5. 保存分块级 JSON 和文本缓存。
6. 将分块文本合并为每个音频一份 `raw/transcript.raw.md`。
7. 写入 `lesson.json`，记录状态、分块数量、预估时长和完成时间。
8. 将已完成文字稿导出到集中 `transcripts/` 文件夹。

## 断点续跑

这套流程支持断点续跑。

如果任务因为网络中断、额度不足、欠费、进程退出等原因停止，用同样的命令和同一个 `--out-root` 再跑一次即可。

重新运行时：

- `lesson.json` 状态为 `done` 的音频会被跳过
- 已写入的分块缓存会被复用
- 未完成的课程会从缺失分块继续
- 最终集中导出文件可以随时重新生成

## 收集最终文字稿

批量转录完成后，把所有已完成课程集中整理到一个文件夹：

```powershell
python scripts\collect_transcripts.py --root "$jobRoot"
```

该命令会生成：

```text
$jobRoot/
  transcripts/
    index.md
    index.json
    part2.raw.combined.md
    <one-file-per-audio>.raw.md
```

最终阅读和导出应使用 `transcripts/` 文件夹。分块目录只是内部证据和断点缓存。

## 可选清理层

清理层必须在原始文字稿存在之后再运行。

短音频端到端样例：

```powershell
python scripts\run_short_audio_pipeline.py `
  --title "sample-title" `
  --audio "D:\path\to\short-sample.mp3"
```

从清理稿生成阅读笔记：

```powershell
python scripts\deepseek_notes_from_cleaned.py --job-dir "D:\path\to\job"
```

建议始终分层保存：

- `raw/transcript.raw.md`：ASR 原始稿，最贴近音频来源
- `cleaned/transcript.cleaned.md`：标点、分段和可读性清理
- `notes/notes.source-faithful.md`：忠实原内容的阅读笔记
- `summary.processed.md`：可选的进一步提炼或改写

## 输出规则

所有重要输出都应包含：

- 版本说明
- 来源或证据说明
- 来源文件或来源 URI
- 边界说明，明确当前文件是原始 ASR、清理稿、阅读笔记还是加工总结

不要把原始 ASR 当成事实核验结果。除非后续复核层明确加入外部引用，否则文字稿内容只代表音频转录结果。

## 校验清单

交付前先重新收集一次：

```powershell
python scripts\collect_transcripts.py --root "$jobRoot"
```

然后检查：

- `lesson.json` 数量等于输入音频数量
- 每个 `lesson.json` 的状态都是 `done`
- `transcripts/` 中每个输入音频都有一份 `.raw.md`
- `part2.raw.combined.md` 存在
- `index.json` 可以按 UTF-8 JSON 正常解析
- 最终文字稿包含 `## Version Note` 和 `## Source / Evidence Note`
- 最终文字稿不包含内部 chunk 标记

JSON 校验示例：

```powershell
python -c "from pathlib import Path; import json; p=Path(r'D:\path\to\job\transcripts\index.json'); d=json.loads(p.read_text(encoding='utf-8')); print(d['completed'], len(d['items']))"
```

如果 PowerShell 中出现中文乱码，不要立刻判断文件损坏。应先用 Python 按 UTF-8 读取，或用支持 UTF-8 的编辑器打开确认。

## 典型端到端命令

```powershell
cd D:\path\to\standalone-skill-xiaoe-audio-transcript-pipeline-v01

$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')

python scripts\dashscope_smoke_test.py --model qwen-plus
python scripts\dashscope_asr_smoke_test.py --audio "D:\path\to\short-sample.mp3" --model qwen3-asr-flash

$jobRoot = "D:\path\to\jobs\audio-transcript-YYYYMMDD-v01"

python scripts\transcribe_local_mp3_batch.py `
  --input-dir "D:\path\to\audio-folder" `
  --out-root "$jobRoot" `
  --model qwen3-asr-flash

python scripts\collect_transcripts.py --root "$jobRoot"
```

最终面向使用者的文字稿位于：

```text
$jobRoot\transcripts\
```
