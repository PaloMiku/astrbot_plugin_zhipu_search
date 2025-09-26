from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from typing import Dict, Optional, Any
import json

try:
    from zai import ZhipuAiClient
    ZHIPU_AVAILABLE = True
except ImportError:
    ZHIPU_AVAILABLE = False
    logger.warning("zai-sdk 未安装，请运行 pip install zai-sdk>=0.0.3.3")

@register(
    "zhipu_search", 
    "PaloMiku", 
    "智谱AI联网搜索插件，专为LLM工具函数设计", 
    "1.0.0", 
    "https://github.com/PaloMiku/astrbot_plugin_zhipu_search"
)
class ZhipuSearchPlugin(Star):
    """智谱AI搜索插件类，提供LLM工具函数支持的联网搜索能力"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        """初始化插件实例
        
        Args:
            context: AstrBot上下文对象
            config: 插件配置对象
        """
        super().__init__(context)
        self.config = config
        self.client = None

        if not ZHIPU_AVAILABLE:
            logger.error("智谱AI SDK未安装，插件无法正常工作，请运行: pip install zai-sdk>=0.0.3.3")
            return
            
        api_key = self.config.get("api_key", "")
        if not api_key:
            logger.warning("未配置智谱AI API Key，请在插件配置中设置")
            return
            
        try:
            self.client = ZhipuAiClient(api_key=api_key)
            logger.info("智谱AI搜索插件初始化成功")
        except Exception as e:
            logger.error(f"智谱AI客户端初始化失败: {e}")
            self.client = None

    async def _web_search(
        self, 
        query: str, 
        search_engine: Optional[str] = None,
        count: Optional[int] = None,
        search_domain_filter: Optional[str] = None,
        search_recency_filter: str = "noLimit",
        content_size: Optional[str] = None
    ) -> Dict[str, Any]:
        """执行智谱AI网络搜索
        
        Args:
            query: 搜索查询关键词
            search_engine: 搜索引擎类型(search_std/search_pro/search_pro_sogou/search_pro_quark)
            count: 返回结果数量(1-50)
            search_domain_filter: 指定搜索域名过滤
            search_recency_filter: 时间范围过滤(noLimit/pastDay/pastWeek/pastMonth/pastYear)
            content_size: 网页摘要字数(low/medium/high)
            
        Returns:
            Dict[str, Any]: 智谱AI搜索API响应结果
            
        Raises:
            Exception: 当客户端未初始化或搜索请求失败时
        """
        if not self.client:
            raise Exception("智谱AI客户端未初始化，请检查API Key配置")
        
        search_engine = search_engine or self.config.get("default_search_engine", "search_pro")
        count = max(1, min(50, count or self.config.get("default_count", 5)))
        content_size = content_size or self.config.get("default_content_size", "medium")
        
        try:
            logger.debug(f"开始搜索: {query}, 引擎: {search_engine}, 数量: {count}")
            response = self.client.web_search.web_search(
                search_engine=search_engine,
                search_query=query,
                count=count,
                search_domain_filter=search_domain_filter,
                search_recency_filter=search_recency_filter,
                content_size=content_size
            )
            return response
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg:
                logger.error(f"API认证失败 (401): {error_msg}")
                logger.error("请检查：1) API Key是否正确 2) 账户余额是否充足 3) 是否开通了网络搜索功能")
            elif "403" in error_msg:
                logger.error(f"API权限不足 (403): {error_msg}")
                logger.error("请检查账户是否开通了网络搜索功能")
            elif "429" in error_msg:
                logger.error(f"API请求频率超限 (429): {error_msg}")
            else:
                logger.error(f"搜索请求失败: {error_msg}")
            raise

    def _format_search_results_for_llm(self, search_response: Dict[str, Any]) -> str:
        """格式化搜索结果为LLM专用格式
        
        Args:
            search_response: 智谱AI搜索API响应结果
            
        Returns:
            str: 结构化的JSON字符串，供LLM处理使用
        """
        if not search_response or "search_result" not in search_response:
            logger.warning("搜索响应为空或格式不正确")
            return json.dumps({"error": "未找到搜索结果"}, ensure_ascii=False)
        
        results = search_response["search_result"]
        if not results:
            logger.info("搜索返回空结果")
            return json.dumps({"message": "未找到搜索结果"}, ensure_ascii=False)
        
        structured_results = []
        for i, result in enumerate(results, 1):
            structured_result = {
                "序号": i,
                "标题": result.get("title", "").strip(),
                "内容": result.get("content", "").strip(),
                "来源": result.get("media", "").strip(),
                "链接": result.get("link", "").strip(),
                "发布时间": result.get("publish_date", "").strip()
            }
            structured_results.append(structured_result)
        
        logger.info(f"成功格式化{len(structured_results)}条搜索结果")
        return json.dumps(structured_results, ensure_ascii=False, indent=2)

    @filter.llm_tool(name="zhipu_web_search")
    async def llm_web_search_tool(
        self, 
        event: AstrMessageEvent, 
        query: str, 
        count: int = 5
    ) -> MessageEventResult:
        """LLM工具函数：智谱AI网络搜索
        
        此函数会被LLM自动调用，用于获取实时网络信息。
        每次调用确保只执行一次搜索API请求，避免重复消耗。
        
        Args:
            query(string): 搜索查询关键词，描述需要搜索的内容
            count(number): 返回搜索结果的数量，范围1-10，默认5
            
        Returns:
            MessageEventResult: 格式化的搜索结果，供LLM进一步处理
        """
        if not self.config.get("enable_llm_tool", True):
            logger.warning("LLM搜索工具函数已被禁用")
            yield event.plain_result("搜索工具函数已被禁用")
            return
            
        # 详细的状态检查和日志
        logger.info(f"ZHIPU_AVAILABLE: {ZHIPU_AVAILABLE}")
        logger.info(f"client状态: {self.client is not None}")
        api_key = self.config.get("api_key", "")
        logger.info(f"API Key配置状态: {'已配置' if api_key else '未配置'}")
        
        if not ZHIPU_AVAILABLE:
            logger.error("智谱AI SDK未安装")
            yield event.plain_result("智谱AI SDK未安装，请运行: pip install zai-sdk>=0.0.3.3")
            return
            
        if not self.client:
            logger.error("智谱AI客户端未初始化")
            yield event.plain_result("智谱AI客户端未初始化，请检查API Key设置")
            return
        
        count = max(1, min(10, count))
        logger.info(f"LLM工具函数被调用: 查询='{query}', 数量={count}")
        
        try:
            search_response = await self._web_search(query=query, count=count)
            
            if search_response and "search_result" in search_response:
                results = search_response["search_result"]
                if results:
                    result_json = self._format_search_results_for_llm(search_response)
                    
                    search_prompt = self.config.get(
                        "tool_search_prompt", 
                        "你是一个专业的信息搜索助手。请基于搜索结果{search_result}提供准确、全面的回答，并引用相关来源。"
                    )
                    
                    final_result = search_prompt.replace("{search_result}", result_json)
                    
                    logger.info(f"智谱AI搜索API调用成功: 查询'{query}', 返回{len(results)}条结果")
                    yield event.plain_result(final_result)
                else:
                    logger.info(f"搜索'{query}'未找到结果")
                    yield event.plain_result(f"搜索'{query}'未找到相关结果")
            else:
                logger.warning(f"搜索'{query}'响应格式异常")
                yield event.plain_result(f"搜索'{query}'未返回有效结果")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM搜索工具执行失败: {error_msg}")
            
            if "401" in error_msg:
                yield event.plain_result("搜索失败：API Key验证错误，请检查配置中的API Key是否正确，或者账户余额是否充足")
            elif "403" in error_msg:
                yield event.plain_result("搜索失败：API权限不足，请检查账户是否开通了网络搜索功能")  
            elif "429" in error_msg:
                yield event.plain_result("搜索失败：API请求频率超限，请稍后再试")
            else:
                yield event.plain_result(f"搜索工具执行失败: {error_msg}")

    @filter.command("zhipu_config")
    async def show_config(self, event: AstrMessageEvent):
        """显示智谱AI搜索插件配置信息
        
        用于查看插件当前配置状态，包括API Key设置、搜索引擎配置等。
        """
        config_info = [
            "🔧 智谱AI搜索插件配置",
            "=" * 35
        ]
        
        api_key = self.config.get("api_key", "")
        config_info.extend([
            f"API Key: {'✅ 已设置' if api_key else '❌ 未设置'}",
            f"默认搜索引擎: {self.config.get('default_search_engine', 'search_pro')}",
            f"默认结果数量: {self.config.get('default_count', 5)}",
            f"默认内容大小: {self.config.get('default_content_size', 'medium')}",
            f"LLM工具函数: {'✅ 已启用' if self.config.get('enable_llm_tool', True) else '❌ 已禁用'}",
            f"智谱AI SDK: {'✅ 已安装' if ZHIPU_AVAILABLE else '❌ 未安装'}",
            f"客户端状态: {'✅ 已初始化' if self.client else '❌ 未初始化'}"
        ])
        
        config_info.extend([
            "=" * 35,
            "ℹ️  本插件仅支持LLM工具函数调用",
            "当AI需要搜索信息时会自动触发"
        ])
        
        yield event.plain_result("\n".join(config_info))

    async def terminate(self):
        """插件终止时的清理工作
        
        释放客户端资源，记录插件停用日志。
        """
        if self.client:
            self.client = None
        logger.info("智谱AI搜索插件已停用")
