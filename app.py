"""
班号批量替换工具 v5 - 支持自定义字体
功能：智能文本替换，支持上传自定义字体确保完美显示
作者：微酱
"""

import streamlit as st
import pymupdf
import zipfile
import io
import re
import os
from datetime import datetime
import tempfile

st.set_page_config(
    page_title="班号批量替换工具",
    page_icon="📝",
    layout="wide"
)

st.title("📝 班号批量替换工具")
st.markdown("---")

with st.expander("📖 使用说明"):
    st.markdown("""
    ### 功能说明
    智能替换PDF中的班号文本，支持自定义字体
    
    ### 支持的班号格式
    - 3-10位字母或数字的任意组合
    - 例如：B260830、C12345、ABC123
    
    ### 字体设置
    - **推荐上传字体**：上传与原PDF相同的字体文件（如 HarmonyOS Sans SC）
    - 字体格式支持：TTF、OTF
    - 上传字体后可支持任意字符，不会出现显示异常
    
    ### 如果不上传字体
    - 工具会尝试使用PDF内嵌字体
    - 如果新班号包含原字体没有的字符，可能显示为方框
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
st.markdown("### 2️⃣ 上传字体文件（可选但推荐）")

font_file = st.file_uploader(
    "上传字体文件（TTF/OTF）",
    type=["ttf", "otf"],
    help="上传与原PDF相同的字体，确保替换后显示正常。推荐上传 HarmonyOS Sans SC Regular 和 Bold。"
)

if font_file:
    st.success(f"✅ 已上传字体：{font_file.name}")

st.markdown("---")
st.markdown("### 3️⃣ 输入班号")

col1, col2 = st.columns(2)

with col1:
    old_class_numbers = st.text_input(
        "旧班号（要被替换的）",
        placeholder="如：B250675、ABC123、123456"
    )

with col2:
    new_class_numbers = st.text_input(
        "新班号",
        placeholder="如：B260830、ABC456、654321"
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
            st.error(f"❌ 旧班号格式错误：{', '.join(invalid_old)}")
        if invalid_new:
            st.error(f"❌ 新班号格式错误：{', '.join(invalid_new)}")
        
        if not invalid_old and not invalid_new:
            st.success("✅ 班号格式正确")
            
            for old, new in zip(old_numbers, new_numbers):
                if len(old) != len(new):
                    st.warning(f"⚠️ {old}（{len(old)}位）→ {new}（{len(new)}位）：长度不一致")

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

def replace_text_with_font(page, old_text, new_text, font_buffer=None, font_name=None):
    """使用指定字体替换文本"""
    replacements = 0
    bg_color = (1, 1, 1)
    
    text_dict = page.get_text("dict")
    
    for block in text_dict.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if old_text in text:
                    bbox = span.get("bbox")
                    if not bbox:
                        continue
                    
                    rect = pymupdf.Rect(bbox)
                    size = span.get("size", 11)
                    origin = span.get("origin", (bbox[0], bbox[1]))
                    
                    color = span.get("color", 0)
                    if isinstance(color, int):
                        r = ((color >> 16) & 0xFF) / 255.0
                        g = ((color >> 8) & 0xFF) / 255.0
                        b = (color & 0xFF) / 255.0
                        color_tuple = (r, g, b)
                    else:
                        color_tuple = (0, 0, 0)
                    
                    # 覆盖原文本
                    shape = page.new_shape()
                    shape.draw_rect(rect)
                    shape.finish(fill=bg_color, color=bg_color)
                    shape.commit()
                    
                    new_full_text = text.replace(old_text, new_text)
                    
                    # 如果有上传字体，使用自定义字体
                    if font_buffer and font_name:
                        try:
                            # 插入字体到页面
                            font_xref = page.insert_font(fontname=font_name, fontbuffer=font_buffer)
                            # 使用自定义字体插入文本
                            page.insert_text(
                                (bbox[0], origin[1]),
                                new_full_text,
                                fontname=font_name,
                                fontsize=size,
                                color=color_tuple
                            )
                            replacements += 1
                            continue
                        except Exception as e:
                            pass
                    
                    # 如果没有字体或失败，尝试使用原字体
                    font = span.get("font", "helv")
                    try:
                        page.insert_text(
                            (bbox[0], origin[1]),
                            new_full_text,
                            fontname=font,
                            fontsize=size,
                            color=color_tuple
                        )
                        replacements += 1
                    except:
                        for fallback_font in ["helv", "arial", "times-roman"]:
                            try:
                                page.insert_text(
                                    (bbox[0], origin[1]),
                                    new_full_text,
                                    fontname=fallback_font,
                                    fontsize=size,
                                    color=color_tuple
                                )
                                replacements += 1
                                break
                            except:
                                continue
    
    return replacements

def replace_text_smart(page, old_text, new_text):
    """直接修改PDF内容流（最无痕）"""
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

if st.button("🚀 开始替换", disabled=not can_process, type="primary"):
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed_files = []
    success_count = 0
    error_count = 0
    
    replace_map = dict(zip(old_numbers, new_numbers))
    
    # 处理字体文件
    font_buffer = None
    font_name = None
    if font_file:
        font_buffer = font_file.read()
        font_name = os.path.splitext(font_file.name)[0]
        status_text.text(f"已加载字体：{font_name}")
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            status_text.text(f"正在处理：{uploaded_file.name} ({i+1}/{len(uploaded_files)})")
            
            pdf_bytes = uploaded_file.read()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            
            total_replacements = 0
            
            for page in doc:
                for old_num, new_num in replace_map.items():
                    # 优先使用内容流替换（最无痕）
                    if not font_file:  # 只有没上传字体时才尝试
                        reps = replace_text_smart(page, old_num, new_num)
                        if reps > 0:
                            total_replacements += reps
                            continue
                    
                    # 使用字体替换
                    reps = replace_text_with_font(page, old_num, new_num, font_buffer, font_name)
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
    Made with ❤️ by 微酱 | v5.0 支持自定义字体版
</div>
""", unsafe_allow_html=True)
