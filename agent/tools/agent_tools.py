import os.path
import random
import requests
import time

from typing import Optional, List

from langchain.tools import StructuredTool

from rag.rag_service import RagSummarizeService
from rag.vector_store import VectorStoreService

from utils.logger_handler import logger
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path


user_id = [
    "1001", "1002", "1003", "1004", "1005",
    "1006", "1007", "1008", "1009", "1010",
]

month_arr = [
    "2025-01", "2025-02", "2025-03",
    "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09",
    "2025-10", "2025-11", "2025-12"
]

rag = RagSummarizeService()

vector_store = VectorStoreService()

GAODE_KEY = agent_conf.get("gaode_key", "")

external_data = {}

# 模拟工单数据
mock_tickets = {
    "TICKET001": {
        "title": "设备故障报修",
        "status": "处理中",
        "priority": "高",
        "created_at": "2025-06-01",
        "assignee": "张三"
    },
    "TICKET002": {
        "title": "功能需求申请",
        "status": "已完成",
        "priority": "中",
        "created_at": "2025-05-15",
        "assignee": "李四"
    },
    "TICKET003": {
        "title": "数据同步异常",
        "status": "待处理",
        "priority": "紧急",
        "created_at": "2025-06-10",
        "assignee": "王五"
    },
    "TICKET004": {
        "title": "系统性能优化",
        "status": "处理中",
        "priority": "中",
        "created_at": "2025-06-05",
        "assignee": "张三"
    },
}

# 模拟系统统计数据
mock_system_stats = {
    "total_users": 12580,
    "active_users": 3420,
    "total_tickets": 892,
    "resolved_tickets": 756,
    "pending_tickets": 136,
    "system_uptime": "99.8%",
    "avg_response_time": "2.3秒",
}


def retry_with_backoff(
        max_retries=3,
        delay=1,
        backoff_factor=2
):
    def decorator(func):

        def wrapper(*args, **kwargs):

            retries = 0
            current_delay = delay

            while retries < max_retries:

                try:
                    return func(*args, **kwargs)

                except Exception as e:

                    retries += 1

                    logger.warning(
                        f"调用{func.__name__}失败，"
                        f"第{retries}次重试，"
                        f"错误: {str(e)}"
                    )

                    if retries < max_retries:

                        time.sleep(current_delay)

                        current_delay *= backoff_factor

                    else:

                        logger.error(
                            f"调用{func.__name__}失败，"
                            f"已达最大重试次数{max_retries}"
                        )

                        raise

        return wrapper

    return decorator


# =========================
# RAG 检索
# =========================

def rag_search(
        query: str,
        source: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 5
) -> str:
    """
    从知识库向量存储中检索参考资料
    """

    try:

        retriever = vector_store.get_retriever(
            retriever_type="hybrid"
        )

        if retriever is None:
            return "知识库检索器初始化失败"

        full_query = query

        if keywords:
            full_query += " " + " ".join(keywords)

        results = retriever.invoke(full_query)

        if source:
            results = [
                r for r in results
                if r.metadata.get("source") == source
            ]

        context = ""

        for idx, doc in enumerate(results[:limit], start=1):

            context += (
                f"[参考资料{idx}]\n"
                f"来源: {doc.metadata.get('source', '未知')}\n"
                f"内容: {doc.page_content}\n\n"
            )

        if not context:
            return "未检索到相关资料"

        return context

    except Exception as e:

        logger.error(f"RAG检索失败: {str(e)}")

        return "检索参考资料时出现错误"


# =========================
# 天气
# =========================

@retry_with_backoff(max_retries=3, delay=1)
def get_weather(city: Optional[str] = None) -> str:

    if not GAODE_KEY:

        logger.error("高德地图API密钥未配置")

        return "天气服务暂不可用"

    try:

        ip_res = requests.get(
            f"https://restapi.amap.com/v3/ip?key={GAODE_KEY}",
            timeout=10
        )

        ip_res.raise_for_status()

        ip_data = ip_res.json()

        if city is None:
            city = ip_data.get("city", "北京")

        if not city:
            city = "北京"

        weather_res = requests.get(
            "https://restapi.amap.com/v3/weather/weatherInfo",
            params={
                "key": GAODE_KEY,
                "city": city,
                "extensions": "base"
            },
            timeout=10
        )

        weather_res.raise_for_status()

        weather_data = weather_res.json()

        if "lives" not in weather_data:
            return f"未获取到{city}天气信息"

        if not weather_data["lives"]:
            return f"未获取到{city}天气信息"

        w = weather_data["lives"][0]

        return (
            f"{w['city']} "
            f"{w['weather']}，"
            f"温度{w['temperature']}℃，"
            f"{w['winddirection']}{w['windpower']}级"
        )

    except Exception as e:

        logger.error(f"获取天气失败: {str(e)}")

        return "获取天气失败"


# =========================
# 用户位置
# =========================

@retry_with_backoff(max_retries=3, delay=1)
def get_user_location() -> str:

    if not GAODE_KEY:
        return "未知城市"

    try:

        res = requests.get(
            f"https://restapi.amap.com/v3/ip?key={GAODE_KEY}",
            timeout=10
        )

        res.raise_for_status()

        data = res.json()

        city = data.get("city", "未知城市")

        return city if city else "未知城市"

    except Exception as e:

        logger.error(f"获取用户位置失败: {str(e)}")

        return "未知城市"


# =========================
# 用户ID
# =========================

def get_user_id() -> str:
    return random.choice(user_id)


# =========================
# 当前月份
# =========================

def get_current_month() -> str:
    return random.choice(month_arr)


# =========================
# 外部数据
# =========================

def generate_external_data():

    if external_data:
        return

    try:

        external_data_path = get_abs_path(
            agent_conf["external_data_path"]
        )

        if not os.path.exists(external_data_path):

            raise FileNotFoundError(
                f"外部数据文件不存在: {external_data_path}"
            )

        with open(
                external_data_path,
                "r",
                encoding="utf-8"
        ) as f:

            for line in f.readlines()[1:]:

                line = line.strip()

                if not line:
                    continue

                arr = line.split(",")

                if len(arr) < 6:

                    logger.warning(f"数据格式错误: {line}")

                    continue

                uid = arr[0].strip('"')
                feature = arr[1].strip('"')
                efficiency = arr[2].strip('"')
                consumables = arr[3].strip('"')
                comparison = arr[4].strip('"')
                time_val = arr[5].strip('"')

                if uid not in external_data:
                    external_data[uid] = {}

                external_data[uid][time_val] = {
                    "特征": feature,
                    "效率": efficiency,
                    "耗材": consumables,
                    "对比": comparison,
                }

    except Exception as e:

        logger.error(f"加载外部数据失败: {str(e)}")


# =========================
# 获取外部数据
# =========================

def fetch_external_data(
        user_id_param: str,
        month: str
) -> str:

    try:

        generate_external_data()

        if user_id_param not in external_data:
            return ""

        if month not in external_data[user_id_param]:
            return ""

        return str(
            external_data[user_id_param][month]
        )

    except Exception as e:

        logger.error(f"获取外部数据失败: {str(e)}")

        return ""


# =========================
# 报告上下文
# =========================

def fill_context_for_report() -> str:
    return "fill_context_for_report已调用"


# =========================
# 工单查询
# =========================

def query_ticket(
        ticket_id: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None
) -> str:

    try:

        results = []

        for tid, info in mock_tickets.items():

            match = True

            if ticket_id and tid != ticket_id:
                match = False

            if status and info["status"] != status:
                match = False

            if priority and info["priority"] != priority:
                match = False

            if assignee and info["assignee"] != assignee:
                match = False

            if match:

                results.append({
                    "工单ID": tid,
                    "标题": info["title"],
                    "状态": info["status"],
                    "优先级": info["priority"],
                    "创建时间": info["created_at"],
                    "处理人": info["assignee"]
                })

        if not results:
            return "未找到匹配工单"

        result_str = "查询结果：\n\n"

        for idx, ticket in enumerate(results, start=1):

            result_str += (
                f"{idx}. 工单ID: {ticket['工单ID']}\n"
                f"标题: {ticket['标题']}\n"
                f"状态: {ticket['状态']}\n"
                f"优先级: {ticket['优先级']}\n"
                f"创建时间: {ticket['创建时间']}\n"
                f"处理人: {ticket['处理人']}\n\n"
            )

        return result_str

    except Exception as e:

        logger.error(f"查询工单失败: {str(e)}")

        return "查询工单失败"


# =========================
# 系统统计
# =========================

def get_system_stats() -> str:

    try:

        stats = mock_system_stats

        return (
            f"系统统计信息：\n"
            f"总用户数: {stats['total_users']}\n"
            f"活跃用户数: {stats['active_users']}\n"
            f"总工单数: {stats['total_tickets']}\n"
            f"已解决工单: {stats['resolved_tickets']}\n"
            f"待处理工单: {stats['pending_tickets']}\n"
            f"系统可用性: {stats['system_uptime']}\n"
            f"平均响应时间: {stats['avg_response_time']}"
        )

    except Exception as e:

        logger.error(f"获取系统统计失败: {str(e)}")

        return "获取系统统计失败"


# =========================
# StructuredTool 注册
# =========================

rag_search_tool = StructuredTool.from_function(
    func=rag_search,
    name="rag_search",
    description="从知识库中检索相关资料"
)

get_weather_tool = StructuredTool.from_function(
    func=get_weather,
    name="get_weather",
    description="获取指定城市天气"
)

get_user_location_tool = StructuredTool.from_function(
    func=get_user_location,
    name="get_user_location",
    description="获取用户所在城市"
)

get_user_id_tool = StructuredTool.from_function(
    func=get_user_id,
    name="get_user_id",
    description="获取用户ID"
)

get_current_month_tool = StructuredTool.from_function(
    func=get_current_month,
    name="get_current_month",
    description="获取当前月份"
)

fetch_external_data_tool = StructuredTool.from_function(
    func=fetch_external_data,
    name="fetch_external_data",
    description="获取用户外部数据"
)

fill_context_for_report_tool = StructuredTool.from_function(
    func=fill_context_for_report,
    name="fill_context_for_report",
    description="填充报告上下文"
)

query_ticket_tool = StructuredTool.from_function(
    func=query_ticket,
    name="query_ticket",
    description="查询工单信息"
)

get_system_stats_tool = StructuredTool.from_function(
    func=get_system_stats,
    name="get_system_stats",
    description="获取系统统计信息"
)

# =========================
# Tool 注册表
# =========================

TOOL_REGISTRY = {
    "rag_search": rag_search_tool,
    "get_weather": get_weather_tool,
    "get_user_location": get_user_location_tool,
    "get_user_id": get_user_id_tool,
    "get_current_month": get_current_month_tool,
    "fetch_external_data": fetch_external_data_tool,
    "fill_context_for_report": fill_context_for_report_tool,
    "query_ticket": query_ticket_tool,
    "get_system_stats": get_system_stats_tool,
}


def get_all_tools() -> List:
    return list(TOOL_REGISTRY.values())


def get_tool_by_name(name: str):
    return TOOL_REGISTRY.get(name)