"""聊天消息组件 - 包含消息显示和用户输入功能"""

import streamlit as st
import logging
from utils.validator import validator
from utils.audit_logger import audit_logger

logger = logging.getLogger(__name__)


def render_chat_area():
    """渲染聊天区域"""
    # 加载当前会话消息
    if st.session_state["current_session_id"] and not st.session_state["message_loaded"]:
        load_session_messages(st.session_state["current_session_id"])

    # 显示对话历史
    if st.session_state["current_session_id"]:
        render_message_history()
    else:
        render_empty_state()

    # 用户输入
    if st.session_state["current_session_id"]:
        handle_user_input()
    else:
        st.chat_input("请先创建新会话", disabled=True)


def render_message_history():
    """渲染消息历史"""
    messages = st.session_state.get("message", [])
    
    if not messages:
        st.info("开始新的对话吧！我可以帮助您解答关于公司制度、产品服务等方面的问题。")
        return
    
    # 遍历消息并显示
    for idx, message in enumerate(messages):
        with st.chat_message(message["role"]):
            # 添加消息序号和时间戳（如果有）
            if message.get("timestamp"):
                st.caption(message["timestamp"])
            
            # 显示消息内容
            st.write(message["content"])
            
            # 对于助手回复，可以添加一些额外信息
            if message["role"] == "assistant" and idx > 0:
                # 显示来源信息（如果有）
                if "sources" in message:
                    with st.expander("查看参考来源"):
                        for i, source in enumerate(message["sources"], 1):
                            st.write(f"{i}. {source}")


def render_empty_state():
    """渲染空状态"""
    st.info("暂无会话，请先创建新会话或选择历史会话")
    
    # 添加一些欢迎信息
    st.markdown("""
    欢迎使用企业级智能客服与知识管理系统！
    
    **主要功能：**
    - 📝 多轮会话管理
    - 📁 知识库文档上传
    - 🔍 智能问答检索
    - 💾 会话持久化存储
    
    点击左侧「新建会话」开始您的咨询之旅。
    """)


def handle_user_input():
    """处理用户输入"""
    prompt = st.chat_input("请输入您的问题...")

    if prompt:
        # 输入验证
        valid, error, cleaned_prompt = validator.validate_user_input(prompt)
        
        if not valid:
            st.error(f"输入验证失败: {error}")
            return
        
        # 获取用户ID用于审计日志
        user_id = st.session_state["current_user"]["id"] if st.session_state.get("current_user") else None
        session_id = st.session_state["current_session_id"]
        
        # 添加用户消息到UI
        st.chat_message("user").write(cleaned_prompt)
        
        # 添加到会话状态
        st.session_state["message"].append({"role": "user", "content": cleaned_prompt})

        # 保存到数据库
        success = st.session_state["session_manager"].add_message(
            session_id,
            "user",
            cleaned_prompt
        )
        
        if not success:
            st.error("保存消息失败")
            return
        
        # 记录审计日志
        audit_logger.log_message_send(user_id, session_id, cleaned_prompt)
        
        # 更新会话标题（在发送用户消息后立即更新，用于第一条消息）
        title_updated = update_session_title(cleaned_prompt)

        # 获取助手响应
        response_message = []
        with st.spinner("思考中..."):
            try:
                res_stream = st.session_state["agent"].execute_stream(cleaned_prompt)

                def capture(generator, cache_list):
                    for chunk in generator:
                        cache_list.append(chunk)
                        yield chunk

                st.chat_message("assistant").write_stream(capture(res_stream, response_message))
                
                if response_message:
                    assistant_response = response_message[-1]
                    st.session_state["message"].append({"role": "assistant", "content": assistant_response})

                    # 保存到数据库
                    success = st.session_state["session_manager"].add_message(
                        session_id,
                        "assistant",
                        assistant_response
                    )
                    
                    if not success:
                        st.warning("保存响应失败")
                    
                    # 如果标题已更新，在响应完成后刷新页面显示新标题
                    if title_updated:
                        logger.info("Calling st.rerun() to refresh session title in sidebar")
                        st.rerun()
                else:
                    st.error("未能获取到响应，请重试")
                    audit_logger.log_message_send(user_id, session_id, cleaned_prompt, 
                                                 success=False, error_message="未能获取到响应")
                    
            except Exception as e:
                st.error(f"处理请求时出错: {str(e)}")
                st.session_state["message"].append({"role": "assistant", "content": f"抱歉，处理您的请求时出现错误: {str(e)}"})
                audit_logger.log_message_send(user_id, session_id, cleaned_prompt, 
                                             success=False, error_message=str(e))


def update_session_title(prompt: str) -> bool:
    """更新会话标题（仅在标题为默认值时更新）

    Returns:
        bool: 如果标题被更新返回True，否则返回False
    """
    # 获取当前会话信息
    session_id = st.session_state["current_session_id"]
    session_info = st.session_state["session_manager"].get_session(session_id)

    current_title = session_info.get("title") if session_info else None
    logger.info(f"update_session_title: session_id={session_id}, current_title='{current_title}'")

    # 只有当标题是默认的"新会话"时才更新
    if session_info and current_title == "新会话":
        if len(prompt) > 30:
            title = prompt[:30] + "..."
        else:
            title = prompt

        try:
            success = st.session_state["session_manager"].update_session_title(
                session_id,
                title
            )
            logger.info(f"update_session_title: title updated to '{title}', success={success}")
            return success
        except Exception as e:
            logger.error(f"update_session_title failed: {e}")
            return False

    logger.info(f"update_session_title: skipped, current_title='{current_title}'")
    return False


def load_session_messages(session_id: str):
    """加载会话消息"""
    try:
        messages = st.session_state["session_manager"].get_messages(session_id)
        st.session_state["message"] = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
        st.session_state["agent"].clear_history()
        for msg in messages:
            st.session_state["agent"].add_message(msg["role"], msg["content"])
        st.session_state["message_loaded"] = True
    except Exception as e:
        st.error(f"加载会话消息失败: {str(e)}")
        st.session_state["message"] = []