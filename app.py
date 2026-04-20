"""
班号批量替换工具 v10 - 直接操作PDF文本对象
核心思路：直接修改PDF内容流中的文本，完全无痕
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

st.title("📝 班号批量替换工具 v10")
st.markdown("**直接修改PDF文本，无色块、无痕迹**")
st.markdown("---")

with st.expander("📖 工作原理"):
    st.markdown("""
    ### 核心方法
    直接在PDF内部修改文本内容，就像在编辑器里改字一样
    
    ### 适用情况
    - 新旧班号字符相同 → 完美无痕（如 B250728 → B260830，用到的字符都是 0-9 和 B）
    - 字符不同但长度相同 → 尝试直接替换（效果取决于PDF字体嵌入情况）
    
    ### 注意事项
    - 如果替换后文字显示异常，说明PDF字体没有包含新字符
    - 此时可上传字体文件，工具会使用覆盖重写方式
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
    "上传字体文件（TTF/OTF）- 仅当直接替换失败时使用",
    type=["ttf", "otf"],
    help="如果直接替换后文字显示异常，上传字体文件使用覆盖方式"
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

def check_char_compatibility(old_text, new_text):
    """检查新旧文本的字符兼容性"""
    old_chars = set(old_text)
    new_chars = set(new_text)
    return new_chars.issubset(old_chars)

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
                if check_char_compatibility(old, new):
                    st.info(f"✓ {old} → {new}：字符完全兼容，直接替换无痕迹")
                else:
                    diff = set(new) - set(old)
                    st.warning(f"⚠️ {old} → {new}：新增字符 {diff}，可能需要字体支持")

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


def replace_text_direct(doc, page, old_text, new_text):
    """
    方法1：直接修改PDF内容流中的文本
    这是最干净的方式，不会有任何色块或痕迹
    """
    replacements = 0
    
    try:
        # 获取页面的所有内容流
        for xref in page.get_contents():
            # 读取原始内容流
            content = doc.xref_stream(xref)
            
            if not isinstance(content, bytes):
                continue
            
            # 尝试不同的编码方式
            for encoding in ['latin-1', 'utf-8', 'cp1252']:
                try:
                    content_str = content.decode(encoding)
                    
                    if old_text in content_str:
                        # 直接替换文本
                        new_content = content_str.replace(old_text, new_text)
                        doc.update_stream(xref, new_content.encode(encoding))
                        replacements += content_str.count(old_text)
                        break
                        
                except (UnicodeDecodeError, UnicodeEncodeError):
                    continue
                    
    except Exception as e:
        print(f"直接替换出错: {e}")
    
    return replacements


def replace_with_overlay(doc, page, old_text, new_text, font_buffer=None, font_name=None):
    """
    方法2：覆盖重写（仅当方法1失败时使用）
    精确定位班号位置，只覆盖班号本身
    """
    replacements = 0
    
    # 精确搜索班号位置
    instances = page.search_for(old_text)
    
    if not instances:
        return 0
    
    for rect in instances:
        try:
            # 获取该位置的文本样式
            text_info = page.get_text("dict", clip=rect)
            
            font_size = 12
            text_color = (1, 1, 1)  # 默认白色
            
            for block in text_info.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            font_size = span.get("size", 12)
                            color = span.get("color", 0)
                            if isinstance(color, int):
                                r = ((color >> 16) & 0xFF) / 255.0
                                g = ((color >> 8) & 0xFF) / 255.0
                                b = (color & 0xFF) / 255.0
                                text_color = (r, g, b)
            
            # 方法2A：使用矩形覆盖 + 插入新文字
            # 但这次我们用更智能的方式：获取背景色
            
            # 获取班号周围的背景色
            bg_rect = pymupdf.Rect(rect.x0 - 5, rect.y0 - 5, rect.x1 + 5, rect.y1 + 5)
            bg_samples = []
            
            # 采样背景色
            for dx in [-3, 0, 3]:
                for dy in [-3, 0, 3]:
                    if dx == 0 and dy == 0:
                        continue
                    sample_rect = pymupdf.Rect(
                        rect.x0 + dx - 2,
                        rect.y0 + dy - 2,
                        rect.x0 + dx + 2,
                        rect.y0 + dy + 2
                    )
                    # 确保采样区域在页面内
                    if sample_rect.x0 >= 0 and sample_rect.y0 >= 0:
                        try:
                            pix = page.get_pixmap(matrix=pymupdf.Matrix(1, 1), clip=sample_rect)
                            if pix.n >= 3:
                                # 取中心像素
                                cx, cy = pix.width // 2, pix.height // 2
                                pixel = pix.pixel(cx, cy)
                                bg_samples.append((pixel[0]/255, pixel[1]/255, pixel[2]/255))
                        except:
                            pass
            
            # 计算平均背景色
            if bg_samples:
                bg_color = tuple(sum(c[i] for c in bg_samples) / len(bg_samples) for i in range(3))
            else:
                bg_color = (0.8, 0.2, 0.2)  # 默认红色
            
            # 绘制背景（稍微缩小一点，避免覆盖到"班"字）
            bg_rect_inner = pymupdf.Rect(rect.x0 + 1, rect.y0 + 1, rect.x1 - 1, rect.y1 - 1)
            page.draw_rect(bg_rect_inner, color=bg_color, fill=bg_color)
            
            # 插入新文字
            if font_buffer and font_name:
                try:
                    page.insert_font(fontname=font_name, fontbuffer=font_buffer)
                    page.insert_text(
                        (rect.x0 + 2, rect.y1 - 3),
                        new_text,
                        fontname=font_name,
                        fontsize=font_size,
                        color=text_color
                    )
                except:
                    # 使用内置字体
                    page.insert_text(
                        (rect.x0 + 2, rect.y1 - 3),
                        new_text,
                        fontname="helv",
                        fontsize=font_size,
                        color=text_color
                    )
            else:
                page.insert_text(
                    (rect.x0 + 2, rect.y1 - 3),
                    new_text,
                    fontname="helv",
                    fontsize=font_size,
                    color=text_color
                )
            
            replacements += 1
            
        except Exception as e:
            print(f"覆盖重写出错: {e}")
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
            method_used = []
            
            for page_num, page in enumerate(doc):
                for old_num, new_num in replace_map.items():
                    # 优先方法1：直接修改内容流
                    reps = replace_text_direct(doc, page, old_num, new_num)
                    
                    if reps > 0:
                        method_used.append(f"第{page_num+1}页:直接修改")
                        total_replacements += reps
                    else:
                        # 方法2：覆盖重写（如果上传了字体）
                        if font_buffer:
                            reps = replace_with_overlay(doc, page, old_num, new_num, font_buffer, font_name)
                            if reps > 0:
                                method_used.append(f"第{page_num+1}页:覆盖重写")
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
                "replacements": total_replacements,
                "method": ", ".join(method_used) if method_used else "未替换"
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
                st.text(f"✅ {f['name']} - 替换了 {f['replacements']} 处 ({f['method']})")
    
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
    Made with ❤️ by 微酱 | v10.0 直接操作文本版
</div>
""", unsafe_allow_html=True)
