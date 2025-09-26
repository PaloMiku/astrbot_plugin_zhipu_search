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
    "astrbot_plugin_zhipu_search", 
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
    ) -> Any:
        """执行智谱AI网络搜索
        
        Args:
            query: 搜索查询关键词
            search_engine: 搜索引擎类型(search_std/search_pro/search_pro_sogou/search_pro_quark)
            count: 返回结果数量(1-50)
            search_domain_filter: 指定搜索域名过滤
            search_recency_filter: 时间范围过滤(noLimit/pastDay/pastWeek/pastMonth/pastYear)
            content_size: 网页摘要字数(low/medium/high)
            
        Returns:
            Any: 智谱AI搜索API响应结果 (WebSearchResp对象)
            
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

    def _format_search_results_for_llm(self, search_response) -> str:
        """格式化搜索结果为LLM专用格式
        
        Args:
            search_response: 智谱AI搜索API响应结果
        Returns:
            str: 结构化的JSON字符串，供LLM处理使用
        """

        if hasattr(search_response, 'search_result'):
            results = getattr(search_response, 'search_result', None)
        elif isinstance(search_response, dict) and "search_result" in search_response:
            results = search_response["search_result"]
        else:
            logger.warning(f"搜索响应格式不正确: {type(search_response)}")
            return json.dumps({"error": "未找到搜索结果"}, ensure_ascii=False)
        if not results:
            logger.info("搜索返回空结果")
            return json.dumps({"message": "未找到搜索结果"}, ensure_ascii=False)
        structured_results = []
        for i, result in enumerate(results, 1):

            if hasattr(result, 'title'):
                structured_result = {
                    "序号": i,
                    "标题": getattr(result, 'title', "") or "",
                    "内容": getattr(result, 'content', "") or "",
                    "来源": getattr(result, 'media', "") or "",
                    "链接": getattr(result, 'link', "") or "",
                    "发布时间": getattr(result, 'publish_date', "") or ""
                }
            else:
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
            result_json = self._format_search_results_for_llm(search_response)

            return_to_llm = f"搜索完成！请根据以下搜索结果直接回答用户问题，不要再次搜索：\n\n{result_json}\n\n请立即基于上述搜索结果为用户提供完整的回答。"
            yield return_to_llm
        except Exception as e:
            logger.error(f"LLM搜索工具执行失败: {e}")
            yield event.plain_result(f"搜索失败: {str(e)}")
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
