"""
班号批量替换工具
功能：批量替换PDF文件中的班号文本
作者：微酱
"""

import streamlit as st
import pymupdf
import zipfile
import io
import re
import os
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="班号批量替换工具",
    page_icon="📝",
    layout="wide"
)

# 标题
st.title("📝 班号批量替换工具")
st.markdown("---")

# 使用说明
with st.expander("📖 使用说明"):
    st.markdown("""
    ### 如何使用
    1. **上传PDF文件**：支持批量上传，最多20个文件
    2. **输入班号**：
       - 填写要替换的旧班号（如 `B250675`）
       - 填写新的班号
    3. **点击替换**：系统会自动处理所有文件
    4. **下载结果**：处理完成后可下载所有文件
    
    ### 班号格式
    - 格式：字母 + 6位数字，如 `B250675`、`A123456`
    - 支持多个班号同时替换（用逗号分隔）
    
    ### 注意事项
    - 替换后的文件会自动添加 `_replaced` 后缀
    - 确保新班号长度与旧班号一致（7位），以保持排版
    """)

st.markdown("### 1️⃣ 上传PDF文件")

uploaded_files = st.file_uploader(
    "选择PDF文件（可多选）",
    type=["pdf"],
    accept_multiple_files=True,
    help="支持批量上传，建议每次不超过20个文件"
)

if uploaded_files:
    st.success(f"已上传 {len(uploaded_files)} 个文件")
    
    # 显示文件列表
    with st.expander("📄 查看上传的文件"):
        for i, file in enumerate(uploaded_files, 1):
            st.text(f"{i}. {file.name}")

st.markdown("---")
st.markdown("### 2️⃣ 输入班号")

col1, col2 = st.columns(2)

with col1:
    old_class_numbers = st.text_input(
        "旧班号（要被替换的）",
        placeholder="如：B250675 或 B250675, B250676（多个用逗号分隔）",
        help="输入要替换的班号，多个班号用逗号分隔"
    )

with col2:
    new_class_numbers = st.text_input(
        "新班号",
        placeholder="如：B250676 或 B250676, B250677（多个用逗号分隔）",
        help="输入新的班号，数量需与旧班号一致"
    )

# 解析班号输入
def parse_class_numbers(text):
    """解析班号输入，支持逗号分隔"""
    if not text:
        return []
    # 分割并清理
    numbers = [n.strip().upper() for n in text.split(",")]
    # 过滤空值
    numbers = [n for n in numbers if n]
    return numbers

old_numbers = parse_class_numbers(old_class_numbers)
new_numbers = parse_class_numbers(new_class_numbers)

# 验证班号格式
def validate_class_number(number):
    """验证班号格式：字母+6位数字"""
    pattern = r"^[A-Z][0-9]{6}$"
    return bool(re.match(pattern, number))

if old_numbers and new_numbers:
    # 检查数量是否匹配
    if len(old_numbers) != len(new_numbers):
        st.warning(f"⚠️ 班号数量不匹配：旧班号 {len(old_numbers)} 个，新班号 {len(new_numbers)} 个")
    else:
        # 验证格式
        invalid_old = [n for n in old_numbers if not validate_class_number(n)]
        invalid_new = [n for n in new_numbers if not validate_class_number(n)]
        
        if invalid_old:
            st.error(f"❌ 旧班号格式错误：{', '.join(invalid_old)}（正确格式：字母+6位数字，如B250675）")
        if invalid_new:
            st.error(f"❌ 新班号格式错误：{', '.join(invalid_new)}（正确格式：字母+6位数字，如B250675）")
        
        if not invalid_old and not invalid_new:
            st.success("✅ 班号格式正确")
            
            # 显示替换映射
            with st.expander("🔄 查看替换映射"):
                for old, new in zip(old_numbers, new_numbers):
                    st.text(f"{old} → {new}")

st.markdown("---")
st.markdown("### 3️⃣ 开始替换")

# 替换按钮
can_process = (
    uploaded_files and 
    old_numbers and 
    new_numbers and 
    len(old_numbers) == len(new_numbers) and
    all(validate_class_number(n) for n in old_numbers) and
    all(validate_class_number(n) for n in new_numbers)
)

if st.button("🚀 开始替换", disabled=not can_process, type="primary"):
    
    # 创建进度条
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 处理结果
    processed_files = []
    success_count = 0
    error_count = 0
    
    # 创建替换映射字典
    replace_map = dict(zip(old_numbers, new_numbers))
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            status_text.text(f"正在处理：{uploaded_file.name} ({i+1}/{len(uploaded_files)})")
            
            # 读取PDF
            pdf_bytes = uploaded_file.read()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            
            # 统计替换次数
            total_replacements = 0
            
            # 遍历每一页
            for page in doc:
                for old_num, new_num in replace_map.items():
                    # 搜索文本
                    instances = page.search_for(old_num)
                    
                    for rect in instances:
                        # 添加涂黑标注
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                    
                    # 应用涂黑
                    if instances:
                        page.apply_redactions()
                        
                        # 在原位置插入新文本
                        for rect in instances:
                            page.insert_text(
                                rect.tl,  # 左上角坐标
                                new_num,
                                fontname="helv",
                                fontsize=11,
                                color=(0, 0, 0)
                            )
                        
                        total_replacements += len(instances)
            
            # 生成新文件名
            original_name = uploaded_file.name
            if original_name.endswith(".pdf"):
                new_name = original_name[:-4] + "_replaced.pdf"
            else:
                new_name = original_name + "_replaced.pdf"
            
            # 保存到内存
            output_buffer = io.BytesIO()
            doc.save(output_buffer)
            doc.close()
            
            output_buffer.seek(0)
            processed_files.append({
                "name": new_name,
                "data": output_buffer,
                "replacements": total_replacements
            })
            
            success_count += 1
            
        except Exception as e:
            st.error(f"❌ 处理失败：{uploaded_file.name} - {str(e)}")
            error_count += 1
        
        # 更新进度
        progress_bar.progress((i + 1) / len(uploaded_files))
    
    status_text.text("处理完成！")
    
    # 显示结果统计
    st.markdown("---")
    st.markdown("### 4️⃣ 处理结果")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("成功处理", success_count)
    with col2:
        st.metric("处理失败", error_count)
    with col3:
        total_reps = sum(f["replacements"] for f in processed_files)
        st.metric("总替换次数", total_reps)
    
    # 显示处理详情
    if processed_files:
        with st.expander("📋 查看处理详情"):
            for f in processed_files:
                st.text(f"✅ {f['name']} - 替换了 {f['replacements']} 处")
    
    # 下载按钮
    if len(processed_files) == 1:
        # 单个文件直接下载
        st.download_button(
            label="📥 下载处理后的文件",
            data=processed_files[0]["data"],
            file_name=processed_files[0]["name"],
            mime="application/pdf"
        )
    elif len(processed_files) > 1:
        # 多个文件打包成ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for f in processed_files:
                zip_file.writestr(f["name"], f["data"].getvalue())
        
        zip_buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"班号替换结果_{timestamp}.zip"
        
        st.download_button(
            label="📥 下载所有文件（ZIP压缩包）",
            data=zip_buffer,
            file_name=zip_name,
            mime="application/zip"
        )

# 页脚
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 12px;">
    Made with ❤️ by 微酱 | 如有问题请联系管理员
</div>
""", unsafe_allow_html=True)
