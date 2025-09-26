# AstrBot 智谱AI搜索插件

基于智谱AI Web Search API的AstrBot搜索插件，专为LLM工具函数设计，支持智能联网搜索。

## 功能特性

### 🔍 Web Search API

- 支持多搜索引擎：智谱自研(基础版/高级版)、搜狗、夸克
- 结构化搜索结果返回：标题、摘要、链接、来源、发布时间
- 优化API调用：每次触发仅调用一次搜索接口

### 🤖 LLM工具函数

- 自动集成为LLM可调用的工具函数
- 智能搜索意图识别
- 优化的搜索结果格式供LLM处理
- 确保单次调用，避免重复请求

### 💬 配置管理

- `/zhipu_config` - 查看配置信息

## 配置说明

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `api_key` | 智谱AI API Key | (必填) |
| `default_search_engine` | 默认搜索引擎 | `search_pro` |
| `default_count` | 默认搜索结果数量 | `5` |
| `default_content_size` | 默认网页摘要字数 | `medium` |
| `enable_llm_tool` | 是否启用LLM工具函数 | `true` |
| `tool_search_prompt` | LLM工具搜索提示词模板 | (预设模板) |

### 搜索引擎选项

- `search_std` - 基础版（0.01元/次）
- `search_pro` - 高级版（0.03元/次）
- `search_pro_sogou` - 搜狗（0.05元/次）  
- `search_pro_quark` - 夸克（0.05元/次）

## 使用方法

### LLM工具函数

当启用LLM工具函数时，AI助手将自动在需要时调用搜索功能，每次触发只调用一次API：

```
用户: 请搜索最新的AI技术发展
AI: (自动调用zhipu_web_search工具函数一次) 根据最新搜索结果，AI技术发展...
```

### 配置查看

```
/zhipu_config
```

## API参考

### 核心方法

#### `_web_search()`

执行智谱AI网络搜索，确保单次调用

- `query`: 搜索查询字符串
- `search_engine`: 搜索引擎类型
- `count`: 返回结果数量(1-10)
- `search_domain_filter`: 域名过滤
- `search_recency_filter`: 时间范围过滤
- `content_size`: 摘要内容大小

#### `_format_search_results_for_llm()`

格式化搜索结果为LLM专用JSON格式

- `search_response`: 搜索API响应
- `Returns`: 结构化JSON字符串

## 开发说明

插件基于AstrBot插件开发框架，遵循以下设计原则：

1. **单次API调用**: 确保每次LLM工具函数触发仅调用一次搜索API
2. **异步处理**: 所有网络请求使用async/await
3. **错误容错**: 完善的异常处理和用户友好的错误提示
4. **配置驱动**: 通过配置文件灵活控制插件行为

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！