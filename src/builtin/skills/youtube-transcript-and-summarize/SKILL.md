---
name: youtube-transcript-and-summarize
description: 获取一个或多个 YouTube 视频字幕，并基于字幕内容生成结构化摘要。适合做视频速读、主题归纳、访谈整理和批量内容总结。
triggers:
  - youtube
  - transcript
  - youtube summary
  - video summary
  - 字幕提取
  - 视频总结
  - 视频摘要
---

# youtube-transcript-and-summarize

## 这个技能做什么

这个技能分两步工作：

1. 调用 `youtube-transcript` 工具抓取 YouTube 视频字幕
2. 把抓取结果交给 LLM，生成简洁、结构化的总结

它适合下面这些场景：

- 快速了解单个长视频的核心内容
- 批量比较多个视频的共同主题
- 整理访谈、播客、教学视频的要点
- 在保留失败说明的前提下生成可读摘要

## 什么时候用

当用户提出下面这类需求时，应优先使用这个技能：

- “帮我总结这个 YouTube 视频”
- “把这几个视频的主要观点整理出来”
- “提取字幕并归纳重点”
- “比较多个 YouTube 视频讲了什么”

如果用户要的是：

- 只抓字幕、不需要总结：优先直接用 `youtube-transcript`
- 不是 YouTube 链接：先确认输入是否可被转换为 YouTube 视频 ID 或 URL

## 输入方式

技能至少需要以下三种输入方式之一：

- `input`：单个 YouTube URL 或视频 ID
- `inputs`：多个 URL 或视频 ID，支持逗号分隔或多行文本
- `inputs_file`：文本文件路径，文件中每行一个 URL 或视频 ID

只要三者之一有效，工具即可执行。

### 支持的输入示例

单个 URL：

```json
{
  "input": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

单个视频 ID：

```json
{
  "input": "dQw4w9WgXcQ"
}
```

批量输入：

```json
{
  "inputs": "dQw4w9WgXcQ,https://www.youtube.com/watch?v=aqz-KE-bpKQ"
}
```

文件输入：

```json
{
  "inputs_file": "videos.txt"
}
```

## 可配置参数

下面这些参数会传给 `youtube-transcript` 工具。除非用户有明确要求，否则应优先使用默认值。

### 1. `input`

单个 YouTube URL 或 11 位视频 ID。

- 类型：`string`
- 必填：否，但 `input` / `inputs` / `inputs_file` 三者至少一个必填

### 2. `inputs`

多个 YouTube URL 或视频 ID。

- 类型：`string`
- 必填：否
- 支持格式：逗号分隔或多行分隔

### 3. `inputs_file`

批量输入文件路径。

- 类型：`string`
- 必填：否
- 约定：文件中每行一个 YouTube URL 或视频 ID

### 4. `languages`

字幕语言优先级，传给工具时使用逗号分隔字符串。

- 类型：`string`
- 默认值：`zh-Hans,zh,en,ja`

### 5. `output_dir`

字幕输出目录。

- 类型：`string`
- 默认值：不传

### 6. `workers`

并发工作线程数。

- 类型：`string`
- 默认值：`8`

### 7. `retries`

单个视频抓取失败时的重试次数。

- 类型：`string`
- 默认值：`3`

### 8. `use_cache`

是否复用本地缓存。

- 类型：`string`
- 默认值：`true`
- 推荐值：`true` / `false`

### 9. `max_chars_per_transcript`

单个视频可内联到结果中的最大字幕字符数。超过上限时，摘要只能基于截断后的字幕内容生成。

- 类型：`string`
- 默认值：`12000`

### 10. `summary_output`

可选的 Markdown 摘要输出路径。

- 类型：`string`
- 默认值：不传

## 技能内部固定行为

为了让后续摘要更稳定，这个技能会固定传入以下工具参数：

```yaml
output_mode: plain-text
include_transcript_text: true
dry_run: false
```

这意味着：

- 字幕工具返回纯文本，而不是 JSON
- 返回结果里包含字幕内容，供 LLM 总结
- 这是一次真实执行，不是演练模式

## 执行流程

### Step 1：抓取字幕

调用工具：

```text
youtube-transcript
```

调用参数：

```yaml
input: ${input.input}
inputs: ${input.inputs}
inputs_file: ${input.inputs_file}
languages: ${input.languages}
output_dir: ${input.output_dir}
workers: ${input.workers}
retries: ${input.retries}
use_cache: ${input.use_cache}
output_mode: plain-text
include_transcript_text: true
max_chars_per_transcript: ${input.max_chars_per_transcript}
dry_run: false
```

如果 `input`、`inputs`、`inputs_file` 都为空，工具会直接报错并退出。

### Step 2：生成摘要

调用工具：

```text
llm
```

摘要任务要求：

- 只根据实际拿到的字幕内容总结
- 不编造字幕中不存在的信息
- 如果有多个视频，需要额外归纳共同主题
- 如果字幕缺失、抓取失败或内容被截断，必须明确写在备注里

## 期望输出结构

最终摘要应包含以下部分：

```text
[Overview]
整体主题的简短概述

[Main Ideas]
1. 核心观点
2. 核心观点
3. 核心观点

[Per Video]
- <video id>: 单个视频的一句话摘要

[Notes]
- 哪些视频没有字幕
- 哪些视频抓取失败
- 哪些字幕因长度限制被截断
```

## 使用时要特别注意

- 这个技能依赖外部工具 `youtube-transcript`
- 如果字幕不存在、被地区限制、被平台限制，摘要质量会受影响
- `max_chars_per_transcript` 会直接影响总结完整度
- `use_cache=true` 时，可能复用之前抓取过的结果
- `summary_output` 是技能层的可选输出位置；如果运行环境没有实现额外落盘逻辑，至少要保证在最终回答中返回摘要文本

## 推荐调用心智模型

可以把它理解为：

“先把视频字幕尽量可靠地抓回来，再基于实际字幕内容做保守总结。”

所以这个技能的重点不是“猜视频讲了什么”，而是：

- 尽量按语言优先级抓到字幕
- 对失败和截断保持透明
- 输出结构稳定、便于继续加工

## 自动执行

```text
autoExecuteAllowed: true
```
