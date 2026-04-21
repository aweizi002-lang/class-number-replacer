"""
班号批量替换工具 v12 - 精确替换版
支持上传多个字体文件
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

st.title("📝 班号批量替换工具 v12")
st.markdown("---")

with st.expander("📖 使用说明"):
    st.markdown("""
    ### 为什么需要上传字体？
    PDF中的字体通常是**子集化**的，只包含文档中用到的字符。
    如果新班号包含原文没有的字符，就需要上传完整字体。
    
    ### 使用步骤
    1. 上传PDF文件
    2. 上传字体文件（支持多个，如 Regular 和 Bold）
    3. 输入旧班号和新班号
    4. 点击替换
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
st.markdown("### 2️⃣ 上传字体文件（必须，支持多个）")
font_files = st.file_uploader(
    "上传字体文件（TTF格式，可上传多个）",
    type=["ttf"],
    accept_multiple_files=True,
    help="可上传多个字体文件，如 HarmonyOS Sans SC 和 HarmonyOS Sans SC Bold"
)
if font_files:
    for f in font_files:
        st.text(f"✅ {f.name}")

st.markdown("---")
st.markdown("### 3️⃣ 输入班号")

col1, col2 = st.columns(2)
with col1:
    old_class_numbers = st.text_input("旧班号", placeholder="如：B250728")
with col2:
    new_class_numbers = st.text_input("新班号", placeholder="如：B260830")

def parse_class_numbers(text):
    if not text:
        return []
    numbers = [n.strip().upper() for n in text.split(",")]
    return [n for n in numbers if n]

def validate_class_number(number):
    if not number:
        return False
    return bool(re.match(r"^[A-Z0-9]{3,10}$", number))

old_numbers = parse_class_numbers(old_class_numbers)
new_numbers = parse_class_numbers(new_class_numbers)

if old_numbers and new_numbers:
    if len(old_numbers) != len(new_numbers):
        st.warning("⚠️ 班号数量不匹配")
    else:
        valid = all(validate_class_number(n) for n in old_numbers + new_numbers)
        if valid:
            st.success("✅ 班号格式正确")

st.markdown("---")
st.markdown("### 4️⃣ 开始替换")

can_process = (
    uploaded_files and 
    old_numbers and 
    new_numbers and 
    len(old_numbers) == len(new_numbers) and
    all(validate_class_number(n) for n in old_numbers + new_numbers) and
    font_files is not None and len(font_files) > 0
)

if not font_files and uploaded_files:
    st.warning("⚠️ 请上传字体文件")


def get_pixel_color(page, x, y):
    """获取指定坐标的像素颜色"""
    try:
        rect = pymupdf.Rect(x-2, y-2, x+2, y+2)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=rect)
        cx, cy = pix.width // 2, pix.height // 2
        pixel = pix.pixel(cx, cy)
        return (pixel[0]/255, pixel[1]/255, pixel[2]/255)
    except:
        return None


def get_background_color(page, rect):
    """智能获取背景色"""
    samples = []
    sample_points = [
        (rect.x0 - 5, rect.y0 - 5),
        (rect.x1 + 5, rect.y0 - 5),
        (rect.x0 - 5, rect.y1 + 5),
        (rect.x1 + 5, rect.y1 + 5),
        (rect.x0 - 5, (rect.y0 + rect.y1) / 2),
        (rect.x1 + 5, (rect.y0 + rect.y1) / 2),
    ]
    
    for x, y in sample_points:
        if 0 <= x <= page.rect.width and 0 <= y <= page.rect.height:
            color = get_pixel_color(page, x, y)
            if color:
                samples.append(color)
    
    if samples:
        r_sorted = sorted([s[0] for s in samples])
        g_sorted = sorted([s[1] for s in samples])
        b_sorted = sorted([s[2] for s in samples])
        mid = len(samples) // 2
        return (r_sorted[mid], g_sorted[mid], b_sorted[mid])
    
    return (0.8, 0.2, 0.2)


def replace_class_number(page, old_text, new_text, fonts_data):
    """精确替换班号"""
    replacements = 0
    
    # 搜索所有匹配
    search_patterns = [old_text, old_text + "班"]
    all_instances = []
    
    for pattern in search_patterns:
        for rect in page.search_for(pattern):
            is_dup = any(
                abs(rect.x0 - r.x0) < 10 and abs(rect.y0 - r.y1) < 10 
                for r in all_instances
            )
            if not is_dup:
                all_instances.append(rect)
    
    if not all_instances:
        return 0
    
    for rect in all_instances:
        try:
            text_info = page.get_text("dict", clip=rect)
            
            font_size = 14
            text_color = (1, 1, 1)
            actual_text = ""
            
            for block in text_info.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            actual_text = span.get("text", "")
                            font_size = span.get("size", 14)
                            color = span.get("color", 0)
                            if isinstance(color, int):
                                r = ((color >> 16) & 0xFF) / 255.0
                                g = ((color >> 8) & 0xFF) / 255.0
                                b = (color & 0xFF) / 255.0
                                text_color = (r, g, b)
            
            has_ban = actual_text.endswith("班")
            display_text = new_text + "班" if has_ban else new_text
            
            bg_color = get_background_color(page, rect)
            
            if has_ban and len(actual_text) > len(old_text):
                char_width = (rect.x1 - rect.x0) / len(actual_text)
                cover_width = char_width * len(old_text)
                cover_rect = pymupdf.Rect(
                    rect.x0 - 0.5, rect.y0 - 0.5,
                    rect.x0 + cover_width + 0.5, rect.y1 + 0.5
                )
                insert_x = rect.x0
            else:
                cover_rect = pymupdf.Rect(
                    rect.x0 - 0.5, rect.y0 - 0.5,
                    rect.x1 + 0.5, rect.y1 + 0.5
                )
                insert_x = rect.x0
            
            page.draw_rect(cover_rect, color=bg_color, fill=bg_color)
            
            # 注册所有上传的字体
            for font_name, font_buffer in fonts_data.items():
                try:
                    page.insert_font(fontname=font_name, fontbuffer=font_buffer)
                except:
                    pass
            
            insert_y = rect.y1 - font_size * 0.25
            
            # 尝试使用第一个字体
            primary_font = list(fonts_data.keys())[0] if fonts_data else "helv"
            
            page.insert_text(
                (insert_x, insert_y),
                display_text,
                fontname=primary_font,
                fontsize=font_size,
                color=text_color
            )
            
            replacements += 1
            
        except Exception as e:
            st.text(f"  替换出错: {e}")
    
    return replacements


if st.button("🚀 开始替换", disabled=not can_process, type="primary"):
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed_files = []
    replace_map = dict(zip(old_numbers, new_numbers))
    
    # 读取所有字体
    fonts_data = {}
    for f in font_files:
        font_name = os.path.splitext(f.name)[0].replace(" ", "_")
        fonts_data[font_name] = f.read()
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            status_text.text(f"处理: {uploaded_file.name} ({i+1}/{len(uploaded_files)})")
            
            pdf_bytes = uploaded_file.read()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            
            total_replacements = 0
            
            for page_num, page in enumerate(doc):
                for old_num, new_num in replace_map.items():
                    instances = page.search_for(old_num)
                    if instances:
                        st.text(f"第{page_num+1}页: 找到 {len(instances)} 处 '{old_num}'")
                    
                    reps = replace_class_number(page, old_num, new_num, fonts_data)
                    total_replacements += reps
            
            output_buffer = io.BytesIO()
            doc.save(output_buffer, garbage=4, deflate=True)
            doc.close()
            
            output_buffer.seek(0)
            new_name = uploaded_file.name.replace(".pdf", "_replaced.pdf")
            processed_files.append({
                "name": new_name,
                "data": output_buffer,
                "replacements": total_replacements
            })
            
        except Exception as e:
            st.error(f"处理失败: {uploaded_file.name} - {e}")
        
        progress_bar.progress((i + 1) / len(uploaded_files))
    
    status_text.text("完成！")
    
    st.markdown("---")
    st.markdown("### 5️⃣ 下载结果")
    
    total_reps = sum(f["replacements"] for f in processed_files)
    st.metric("总替换次数", total_reps)
    
    if len(processed_files) == 1:
        st.download_button(
            "📥 下载处理后的文件",
            data=processed_files[0]["data"],
            file_name=processed_files[0]["name"],
            mime="application/pdf"
        )
    elif len(processed_files) > 1:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in processed_files:
                zf.writestr(f["name"], f["data"].getvalue())
        zip_buffer.seek(0)
        
        st.download_button(
            "📥 下载所有文件（ZIP）",
            data=zip_buffer,
            file_name=f"班号替换_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip"
        )

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 12px;">
    Made with ❤️ by 微酱 | v12.0
</div>
""", unsafe_allow_html=True)
