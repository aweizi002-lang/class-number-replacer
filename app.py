"""
班号批量替换工具 v9 - 最精准版
功能：只替换班号，绝对不影响其他内容
作者：微酱
"""

import streamlit as st
import pymupdf
import zipfile
import io
import re
import os
from datetime import datetime

st.set_page_config(
    page_title="班号批量替换工具",
    page_icon="📝",
    layout="wide"
)

st.title("📝 班号批量替换工具")
st.markdown("---")

with st.expander("📖 使用说明"):
    st.markdown("""
    ### 核心原理
    1. **优先级1**：直接修改PDF内部文本内容（完全无痕）
    2. **优先级2**：使用PDF重标注(redact)精准替换
    
    ### 最佳效果
    - 新旧班号字符相同 → 完美无痕（如 B250728 → B260830）
    - 上传字体文件 → 支持任意字符
    
    ### 注意
    - 请确保上传正确的字体文件
    - 如果字符兼容，推荐不上传字体，让系统直接修改
    """)

st.markdown("### 1️⃣ 上传PDF文件")

uploaded_files = st.file_uploader(
    "选择PDF文件（可多选）",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"已上传 {len(uploaded_files)} 个文件")

st.markdown("---")
st.markdown("### 2️⃣ 上传字体文件（可选）")

font_file = st.file_uploader(
    "上传字体文件（TTF/OTF）",
    type=["ttf", "otf"],
    help="如果新旧班号字符不同，需要上传字体"
)

if font_file:
    st.success(f"✅ 已上传字体：{font_file.name}")

st.markdown("---")
st.markdown("### 3️⃣ 输入班号")

col1, col2 = st.columns(2)

with col1:
    old_class_numbers = st.text_input(
        "旧班号",
        placeholder="如：B250675"
    )

with col2:
    new_class_numbers = st.text_input(
        "新班号",
        placeholder="如：B260830"
    )

def parse_class_numbers(text):
    if not text:
        return []
    numbers = [n.strip().upper() for n in text.split(",")]
    return [n for n in numbers if n]

def validate_class_number(number):
    if not number:
        return False
    pattern = r"^[A-Z0-9]{3,10}$"
    return bool(re.match(pattern, number))

old_numbers = parse_class_numbers(old_class_numbers)
new_numbers = parse_class_numbers(new_class_numbers)

if old_numbers and new_numbers:
    if len(old_numbers) != len(new_numbers):
        st.warning(f"⚠️ 班号数量不匹配")
    else:
        invalid_old = [n for n in old_numbers if not validate_class_number(n)]
        invalid_new = [n for n in new_numbers if not validate_class_number(n)]
        
        if invalid_old:
            st.error(f"❌ 旧班号格式错误")
        if invalid_new:
            st.error(f"❌ 新班号格式错误")
        
        if not invalid_old and not invalid_new:
            st.success("✅ 班号格式正确")
            
            for old, new in zip(old_numbers, new_numbers):
                if set(old) == set(new):
                    st.info(f"✓ {old} → {new}：字符兼容，可无痕替换")

st.markdown("---")
st.markdown("### 4️⃣ 开始替换")

can_process = (
    uploaded_files and 
    old_numbers and 
    new_numbers and 
    len(old_numbers) == len(new_numbers) and
    all(validate_class_number(n) for n in old_numbers) and
    all(validate_class_number(n) for n in new_numbers)
)

def replace_in_content_stream(page, old_text, new_text):
    """方法1：直接修改PDF内容流（最无痕）"""
    replacements = 0
    try:
        for xref in page.get_contents():
            content = page.parent.xref_stream(xref)
            if isinstance(content, bytes):
                try:
                    content_str = content.decode('latin-1')
                    if old_text in content_str:
                        new_content = content_str.replace(old_text, new_text)
                        page.parent.update_stream(xref, new_content.encode('latin-1'))
                        replacements += content_str.count(old_text)
                except:
                    pass
    except:
        pass
    return replacements

def replace_with_redact(page, old_text, new_text, font_buffer=None, font_name=None):
    """方法2：使用PDF重标注精准替换"""
    replacements = 0
    
    # 搜索班号位置
    instances = page.search_for(old_text)
    
    if not instances:
        return 0
    
    for rect in instances:
        try:
            # 获取该位置的文本信息
            text_info = page.get_text("dict", clip=rect)
            
            # 提取样式
            font_size = 11
            text_color = (1, 1, 1)
            
            for block in text_info.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            font_size = span.get("size", 11)
                            color = span.get("color", 0)
                            if isinstance(color, int):
                                r = ((color >> 16) & 0xFF) / 255.0
                                g = ((color >> 8) & 0xFF) / 255.0
                                b = (color & 0xFF) / 255.0
                                text_color = (r, g, b)
            
            # 添加重标注（只标记班号位置）
            page.add_redact_annot(rect)
            
            # 应用重标注
            page.apply_redactions()
            
            # 在原位置插入新文本
            if font_buffer and font_name:
                try:
                    page.insert_font(fontname=font_name, fontbuffer=font_buffer)
                    page.insert_text(
                        (rect.x0, rect.y1 - 2),
                        new_text,
                        fontname=font_name,
                        fontsize=font_size,
                        color=text_color
                    )
                except:
                    page.insert_text(
                        (rect.x0, rect.y1 - 2),
                        new_text,
                        fontname="helv",
                        fontsize=font_size,
                        color=text_color
                    )
            else:
                page.insert_text(
                    (rect.x0, rect.y1 - 2),
                    new_text,
                    fontname="helv",
                    fontsize=font_size,
                    color=text_color
                )
            
            replacements += 1
            
        except Exception as e:
            continue
    
    return replacements

if st.button("🚀 开始替换", disabled=not can_process, type="primary"):
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed_files = []
    success_count = 0
    error_count = 0
    
    replace_map = dict(zip(old_numbers, new_numbers))
    
    font_buffer = None
    font_name = None
    if font_file:
        font_buffer = font_file.read()
        font_name = os.path.splitext(font_file.name)[0]
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            status_text.text(f"正在处理：{uploaded_file.name} ({i+1}/{len(uploaded_files)})")
            
            pdf_bytes = uploaded_file.read()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            
            total_replacements = 0
            
            for page in doc:
                for old_num, new_num in replace_map.items():
                    # 优先方法1：直接修改内容流
                    reps = replace_in_content_stream(page, old_num, new_num)
                    
                    if reps == 0:
                        # 方法2：重标注替换
                        reps = replace_with_redact(page, old_num, new_num, font_buffer, font_name)
                    
                    total_replacements += reps
            
            original_name = uploaded_file.name
            new_name = original_name[:-4] + "_replaced.pdf" if original_name.endswith(".pdf") else original_name + "_replaced.pdf"
            
            output_buffer = io.BytesIO()
            doc.save(output_buffer, garbage=4, deflate=True, clean=True)
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
        
        progress_bar.progress((i + 1) / len(uploaded_files))
    
    status_text.text("处理完成！")
    
    st.markdown("---")
    st.markdown("### 5️⃣ 处理结果")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("成功处理", success_count)
    with col2:
        st.metric("处理失败", error_count)
    with col3:
        total_reps = sum(f["replacements"] for f in processed_files)
        st.metric("总替换次数", total_reps)
    
    if processed_files:
        with st.expander("📋 查看处理详情"):
            for f in processed_files:
                st.text(f"✅ {f['name']} - 替换了 {f['replacements']} 处")
    
    if len(processed_files) == 1:
        st.download_button(
            label="📥 下载处理后的文件",
            data=processed_files[0]["data"],
            file_name=processed_files[0]["name"],
            mime="application/pdf"
        )
    elif len(processed_files) > 1:
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

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 12px;">
    Made with ❤️ by 微酱 | v9.0 最精准版
</div>
""", unsafe_allow_html=True)
