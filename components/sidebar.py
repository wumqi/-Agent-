"""侧边栏组件 - 包含会话管理、文档上传等功能"""

import os
import uuid
import streamlit as st
from datetime import datetime
from utils.path_tool import get_abs_path
from utils.audit_logger import audit_logger


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        # 用户信息区域
        render_user_info()
        
        st.divider()
        
        # 会话管理区域
        st.subheader("📋 会话管理")
        
        if st.button("➕ 新建会话", use_container_width=True):
            create_new_session()
        
        # 会话搜索
        search_query = st.text_input(
            "搜索会话",
            placeholder="输入会话标题关键词...",
            key="session_search"
        )
        
        st.divider()
        
        # 历史会话列表
        st.subheader("📝 历史会话")
        render_session_list(search_query)
        
        st.divider()
        
        # 文档上传区域
        st.subheader("📁 文档上传")
        render_document_uploader()
        
        st.divider()
        
        # 操作按钮
        st.subheader("⚙️ 操作")
        render_action_buttons()


def render_user_info():
    """渲染用户信息和登出按钮"""
    if st.session_state.get("current_user"):
        user = st.session_state["current_user"]
        st.subheader("👤 用户信息")
        st.write(f"**用户名**: {user.get('username')}")
        if user.get('email'):
            st.write(f"**邮箱**: {user.get('email')}")
        st.write(f"**角色**: {'管理员' if user.get('role') == 'admin' else '普通用户'}")
        
        if st.button("🚪 登出", use_container_width=True):
            logout_user()


def logout_user():
    """用户登出"""
    user_id = st.session_state["current_user"]["id"] if st.session_state.get("current_user") else None
    audit_logger.log_user_logout(user_id)
    
    # 清除用户相关状态
    st.session_state["logged_in"] = False
    st.session_state["current_user"] = None
    st.session_state["current_session_id"] = None
    st.session_state["message"] = []
    st.session_state["message_loaded"] = False
    
    if "agent" in st.session_state:
        st.session_state["agent"].clear_history()
    
    st.rerun()


def render_session_list(search_query: str = ""):
    """渲染会话列表（支持搜索过滤）"""
    user_id = st.session_state["current_user"]["id"] if st.session_state.get("current_user") else None

    # 强制重新从数据库获取会话列表（不使用缓存），确保显示最新数据
    sessions = st.session_state["session_manager"].get_all_sessions(user_id, use_cache=False)
    
    # 搜索过滤
    if search_query:
        sessions = [
            session for session in sessions 
            if search_query.lower() in session["title"].lower()
        ]
    
    if sessions:
        # 按更新时间排序（最新的在前面）
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        
        for session in sessions:
            col1, col2 = st.columns([4, 1])
            with col1:
                is_current = session["id"] == st.session_state["current_session_id"]
                button_label = f"📌 {session['title']}" if is_current else session['title']
                button_type = "primary" if is_current else "secondary"
                
                if st.button(
                    button_label, 
                    key=f"session_{session['id']}", 
                    use_container_width=True,
                    type=button_type
                ):
                    switch_session(session["id"])
            with col2:
                if st.button(
                    "🗑️", 
                    key=f"delete_{session['id']}",
                    use_container_width=True,
                    help="删除此会话"
                ):
                    delete_session(session["id"])
                    
        # 显示会话数量
        st.caption(f"共 {len(sessions)} 个会话")
    else:
        if search_query:
            st.info("未找到匹配的会话")
        else:
            st.info("暂无历史会话")


def render_document_uploader():
    """渲染文档上传器"""
    uploaded_files = st.file_uploader(
        "上传文档（支持TXT、PDF）",
        type=["txt", "pdf"],
        accept_multiple_files=True,
        help="上传的文档会被添加到知识库中，供智能助手参考",
        key="document_uploader"
    )

    if uploaded_files:
        user_id = st.session_state["current_user"]["id"] if st.session_state.get("current_user") else None
        
        for uploaded_file in uploaded_files:
            temp_dir = get_abs_path("data/uploaded")
            os.makedirs(temp_dir, exist_ok=True)

            file_path = os.path.join(temp_dir, uploaded_file.name)

            # 检查文件是否已存在
            if os.path.exists(file_path):
                st.warning(f"⚠️ {uploaded_file.name} 已存在，将覆盖")

            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            with st.spinner(f"正在处理 {uploaded_file.name}..."):
                try:
                    success = st.session_state["vector_store"].update_document(file_path)
                    if success:
                        st.success(f"✅ {uploaded_file.name} 上传成功！")
                        audit_logger.log_file_upload(user_id, uploaded_file.name, len(uploaded_file.getbuffer()))
                    else:
                        st.error(f"❌ {uploaded_file.name} 上传失败")
                except Exception as e:
                    st.error(f"❌ {uploaded_file.name} 处理出错: {str(e)}")


def render_action_buttons():
    """渲染操作按钮"""
    if st.session_state["current_session_id"]:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ 清空会话", use_container_width=True):
                clear_current_session()
        with col2:
            if st.button("📤 导出会话", use_container_width=True):
                export_session()
    else:
        st.button("🗑️ 清空会话", use_container_width=True, disabled=True)
        st.button("📤 导出会话", use_container_width=True, disabled=True)


def create_new_session():
    """创建新会话"""
    new_session_id = str(uuid.uuid4())
    user_id = st.session_state["current_user"]["id"] if st.session_state.get("current_user") else None
    
    st.session_state["session_manager"].create_session(new_session_id, "新会话", user_id)
    st.session_state["current_session_id"] = new_session_id
    st.session_state["message"] = []
    st.session_state["agent"].clear_history()
    st.session_state["message_loaded"] = True
    st.session_state["session_search"] = ""  # 清空搜索框
    
    audit_logger.log_session_create(user_id, new_session_id)
    st.rerun()


def switch_session(session_id: str):
    """切换会话"""
    st.session_state["current_session_id"] = session_id
    st.session_state["message_loaded"] = False
    load_session_messages(session_id)
    st.rerun()


def delete_session(session_id: str):
    """删除会话"""
    user_id = st.session_state["current_user"]["id"] if st.session_state.get("current_user") else None
    
    st.session_state["session_manager"].delete_session(session_id, current_user_id=user_id)
    audit_logger.log_session_delete(user_id, session_id)
    
    user_id = st.session_state["current_user"]["id"] if st.session_state.get("current_user") else None
    sessions = st.session_state["session_manager"].get_all_sessions(user_id)
    
    if sessions:
        switch_session(sessions[0]["id"])
    else:
        st.session_state["current_session_id"] = None
        st.session_state["message"] = []
        st.session_state["agent"].clear_history()
        st.session_state["message_loaded"] = False
        st.rerun()


def clear_current_session():
    """清空当前会话（删除会话）"""
    session_id = st.session_state["current_session_id"]
    delete_session(session_id)


def load_session_messages(session_id: str):
    """加载会话消息"""
    messages = st.session_state["session_manager"].get_messages(session_id)
    st.session_state["message"] = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
    st.session_state["agent"].clear_history()
    for msg in messages:
        st.session_state["agent"].add_message(msg["role"], msg["content"])
    st.session_state["message_loaded"] = True


def export_session():
    """导出当前会话为TXT格式"""
    session_id = st.session_state["current_session_id"]
    session_info = st.session_state["session_manager"].get_session(session_id)
    messages = st.session_state["message"]
    
    # 处理datetime对象，转换为字符串
    created_at = session_info["created_at"] if session_info else datetime.now()
    updated_at = session_info["updated_at"] if session_info else datetime.now()
    
    # 将datetime转换为字符串
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    elif created_at is not None:
        created_at = str(created_at)
    
    if isinstance(updated_at, datetime):
        updated_at = updated_at.strftime("%Y-%m-%d %H:%M:%S")
    elif updated_at is not None:
        updated_at = str(updated_at)
    
    title = session_info["title"] if session_info else "未命名会话"
    
    # 导出为txt格式，格式与前端显示一致
    lines = []
    lines.append(f"会话标题: {title}")
    lines.append(f"创建时间: {created_at}")
    lines.append(f"更新时间: {updated_at}")
    lines.append("-" * 50)
    lines.append("")
    
    for msg in messages:
        role = "用户" if msg["role"] == "user" else "智能客服"
        lines.append(f"【{role}】")
        lines.append(msg["content"])
        lines.append("")
    
    content = "\n".join(lines)
    
    st.download_button(
        label="📥 下载TXT",
        data=content,
        file_name=f"会话_{title[:10]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        use_container_width=True
    )