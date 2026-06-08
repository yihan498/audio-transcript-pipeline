# 音频转文字工作流

[English README](README.en.md)

把一整个文件夹里的长音频，批量转成可阅读的 Markdown 文字稿。

支持 **长音频切分、国内 ASR 转录、断点续跑、集中导出、可选清理和阅读笔记**。适合课程音频、直播回放、会议录音、访谈录音等批量处理场景。

---

## 核心使用流程

1. 准备一批本地 MP3 音频。
2. 配置 DashScope / DeepSeek 等 API Key。
3. 先跑烟测，确认模型接口和余额可用。
4. 批量转录音频文件夹。
5. 中途失败就用同一个目录重新运行，自动断点续跑。
6. 转录完成后，把所有文字稿集中导出到 `transcripts/`。
7. 可选：基于原始稿生成清理稿、阅读笔记或复核稿。

---

## 功能

| 功能 | 说明 |
|------|------|
| 本地音频批量处理 | 扫描指定文件夹中的 `.mp3` 文件 |
| 长音频切分 | 按 MP3 帧边界切成适合短音频 API 的小块 |
| 国内 ASR 转录 | 默认使用 DashScope / 百炼短音频 ASR |
| 断点续跑 | 已完成课程和分块自动跳过 |
| 集中导出 | 每讲一份 `.raw.md`，并生成一个合并稿 |
| 分层产物 | 原始稿、清理稿、笔记分开保存 |
| 隐私保护 | 音频、文字稿、日志、Key 默认不进仓库 |

---

## 适用场景

适合：

- 课程音频、直播回放、会议录音、访谈录音的批量转文字
- 单个音频较长，不能一次性提交给短音频 ASR
- 希望任务中断后可以继续跑
- 希望最终文字稿统一放在一个文件夹
- 希望后续基于原始稿继续做清理、笔记或总结

不适合：

- 没有音频、字幕或转录来源，只想根据标题生成总结
- 不保留原始转录，直接让模型自由发挥
- 把真实音频或真实转录内容公开到仓库

---

## 工作原理

```text
本地音频文件夹
  → 扫描 MP3
  → 长音频切分
  → 分块调用 ASR
  → 保存分块缓存
  → 合并为每个音频一份原始稿
  → 集中导出到 transcripts/
  → 可选：清理稿 / 阅读笔记 / 复核稿
```

关键点：

- **分块**：长音频会被切成符合 API 限制的小块。
- **缓存**：每个分块结果都会保存，失败后不用从头来。
- **合并**：最终按音频合并成完整文字稿。
- **集中**：最终只需要看 `transcripts/` 文件夹。

---

## 前提条件

- Windows / macOS / Linux 均可，示例命令以 Windows PowerShell 为主
- Python 3.10+
- DashScope / 百炼 API Key
- 可选：DeepSeek API Key

---

## 配置 API Key

PowerShell 中设置：

```powershell
setx DASHSCOPE_API_KEY "your_dashscope_key"
setx DEEPSEEK_API_KEY "your_deepseek_key"
```

`setx` 不会立刻更新当前窗口，所以当前 PowerShell 还需要执行：

```powershell
$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')
```

检查是否生效：

```powershell
python -c "import os; print(bool(os.getenv('DASHSCOPE_API_KEY')))"
python -c "import os; print(bool(os.getenv('DEEPSEEK_API_KEY')))"
```

---

## 快速开始

进入项目目录：

```powershell
cd D:\path\to\audio-transcript-pipeline
```

### 第一步：烟测

测试 DashScope 文本接口：

```powershell
python scripts\dashscope_smoke_test.py --model qwen-plus
```

用一个短音频测试 ASR：

```powershell
python scripts\dashscope_asr_smoke_test.py `
  --audio "D:\path\to\short-sample.mp3" `
  --model qwen3-asr-flash
```

可选：测试 DeepSeek：

```powershell
python scripts\deepseek_smoke_test.py --model deepseek-v4-flash
```

### 第二步：批量转录

```powershell
$jobRoot = "D:\path\to\jobs\audio-transcript-YYYYMMDD-v01"

python scripts\transcribe_local_mp3_batch.py `
  --input-dir "D:\path\to\audio-folder" `
  --out-root "$jobRoot" `
  --model qwen3-asr-flash
```

### 第三步：集中导出

```powershell
python scripts\collect_transcripts.py --root "$jobRoot"
```

最终文字稿位于：

```text
$jobRoot\transcripts\
```

---

## 批量转录参数

```text
--input-dir     本地音频文件夹
--out-root      本次任务输出目录
--model         ASR 模型，默认 qwen3-asr-flash
--max-seconds   每个分块目标秒数，默认 240
--max-bytes     每个分块最大字节数，默认 9500000
--retries       单个分块失败时的重试次数
--limit         只处理前 N 个文件，用于小样本测试
--start-at      从文件名包含某段文本的位置开始
```

---

## 输出格式

一次任务完成后，目录大致如下：

```text
jobRoot/
  <audio-title>/
    chunks/
      chunk_0000.mp3
      chunks-manifest.json
    raw/
      chunk-results/
        chunk_0000.json
        chunk_0000.txt
      transcript.raw.md
    lesson.json
  transcripts/
    index.md
    index.json
    part2.raw.combined.md
    <audio-title>.raw.md
```

推荐阅读：

- `transcripts/index.md`：文字稿目录
- `transcripts/index.json`：机器可读索引
- `transcripts/part2.raw.combined.md`：全部文字稿合并版
- `transcripts/<audio-title>.raw.md`：每个音频单独文字稿

内部文件：

- `chunks/`：音频分块
- `raw/chunk-results/`：分块缓存和 API 原始结果

---

## 断点续跑

如果任务中途停止，用同一个命令、同一个 `--out-root` 再跑一次：

```powershell
python scripts\transcribe_local_mp3_batch.py `
  --input-dir "D:\path\to\audio-folder" `
  --out-root "$jobRoot" `
  --model qwen3-asr-flash
```

脚本会自动：

- 跳过已完成音频
- 复用已完成分块
- 从缺失分块继续
- 允许之后重新生成集中导出

---

## 可选：清理稿和阅读笔记

原始稿生成后，可以继续生成清理稿或笔记。

短音频端到端示例：

```powershell
python scripts\run_short_audio_pipeline.py `
  --title "sample-title" `
  --audio "D:\path\to\short-sample.mp3"
```

从清理稿生成阅读笔记：

```powershell
python scripts\deepseek_notes_from_cleaned.py --job-dir "D:\path\to\job"
```

建议分层保存：

```text
raw/transcript.raw.md              原始 ASR 文字稿
cleaned/transcript.cleaned.md      清理稿
notes/notes.source-faithful.md     忠实原内容的阅读笔记
summary.processed.md               可选提炼稿
```

---

## 校验清单

交付前检查：

- 输入音频数量和 `lesson.json` 数量一致
- 每个 `lesson.json` 的状态都是 `done`
- `transcripts/` 下有对应数量的 `.raw.md`
- `part2.raw.combined.md` 存在
- `index.json` 可以按 UTF-8 JSON 解析
- 最终文字稿不含内部 chunk 标记

JSON 校验示例：

```powershell
python -c "from pathlib import Path; import json; p=Path(r'D:\path\to\job\transcripts\index.json'); d=json.loads(p.read_text(encoding='utf-8')); print(d['completed'], len(d['items']))"
```

---

## 文件结构

```text
audio-transcript-pipeline/
  README.md
  README.zh-CN.md
  README.en.md
  scripts/
  references/
  examples/
  agents/
  .gitignore
```

主要脚本：

| 脚本 | 作用 |
|------|------|
| `transcribe_local_mp3_batch.py` | 批量切分并转录本地 MP3 |
| `collect_transcripts.py` | 收集已完成文字稿 |
| `mp3_frame_splitter.py` | MP3 帧级切分 |
| `dashscope_smoke_test.py` | 测试 DashScope 文本接口 |
| `dashscope_asr_smoke_test.py` | 测试短音频 ASR |
| `deepseek_smoke_test.py` | 测试 DeepSeek |
| `run_short_audio_pipeline.py` | 短音频端到端样例 |
| `deepseek_notes_from_cleaned.py` | 从清理稿生成阅读笔记 |

---

## 常见问题

### `setx` 后 Python 仍然读不到 API Key

当前 PowerShell 窗口需要手动刷新环境变量：

```powershell
$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')
```

### DashScope 无法读取音频 URL

平台签名 URL 可能无法被 ASR 服务访问。建议下载为本地音频后，用 `transcribe_local_mp3_batch.py` 处理。

### 任务中途失败

用同一个 `--out-root` 重新运行。脚本会跳过已完成内容。

### PowerShell 里中文显示乱码

先不要判断文件损坏。用 Python 按 UTF-8 读取，或用支持 UTF-8 的编辑器打开确认。

### 最终文字稿很分散

运行：

```powershell
python scripts\collect_transcripts.py --root "$jobRoot"
```

然后只看：

```text
$jobRoot\transcripts\
```

---

## 隐私

不要提交：

- 音频文件
- 真实文字稿
- `jobs/` 产物
- 分块缓存
- 日志
- `.env`
- API Key
- 浏览器登录状态

`.gitignore` 已默认排除这些类型，提交前仍建议检查。
