#!/usr/bin/env python3
"""
快速教材转换脚本：使用 PyMuPDF (fitz) 批量将 PDF 转为 Markdown
比 markitdown 快很多，适合大批量处理
"""
import os
import sys
import json
import re
import time
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("fast-convert")

BASE_DIR = Path(__file__).resolve().parent.parent
TEXTBOOK_DIR = BASE_DIR / "docs" / "教材"
MARKDOWN_DIR = TEXTBOOK_DIR / "markdown"

# 学科映射
SUBJECT_MAP = {
    "小学语文": "chinese",
    "小学数学": "math",
    "小学英语": "english",
}

def extract_grade(filename):
    """从文件名提取年级"""
    for cn, num in [("一", 1), ("二", 2), ("三", 3), ("四", 4), ("五", 5), ("六", 6)]:
        if f"{cn}年级" in filename:
            return num
    m = re.search(r"(\d+)年级", filename)
    if m:
        return int(m.group(1))
    # 匹配上册/下册
    if "上册" in filename:
        return None  # 需要从上下文推断
    elif "下册" in filename:
        return None
    return 1

def convert_single_pdf(args):
    """转换单个 PDF"""
    pdf_path, output_path = args
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(str(pdf_path))
        text_parts = []
        
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                text_parts.append(f"\n\n--- 第{page_num+1}页 ---\n\n")
                text_parts.append(text)
        
        doc.close()
        
        content = "".join(text_parts)
        
        # 基本清理
        content = re.sub(r'\n{4,}', '\n\n\n', content)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# {pdf_path.stem}\n\n")
            f.write(content)
        
        return (True, str(output_path), len(content))
    except Exception as e:
        return (False, str(pdf_path), str(e))

def get_output_path(pdf_path):
    """根据 PDF 路径生成输出路径"""
    parts = pdf_path.relative_to(TEXTBOOK_DIR).parts
    if len(parts) < 2:
        return None
    
    subject_version = parts[0]
    filename = parts[-1]
    
    subject_key = None
    for key in SUBJECT_MAP:
        if subject_version.startswith(key):
            subject_key = SUBJECT_MAP[key]
            version = subject_version[len(key)+1:]
            break
    
    if not subject_key:
        return None
    
    grade = extract_grade(filename)
    if grade is None:
        # 从路径推断年级
        for part in parts:
            g = extract_grade(part)
            if g:
                grade = g
                break
    
    if grade is None:
        grade = 1
    
    return MARKDOWN_DIR / subject_key / version / f"{grade}年级.md"

def batch_convert(max_workers=4):
    """批量转换所有 PDF"""
    pdf_files = list(TEXTBOOK_DIR.rglob("*.pdf"))
    logger.info(f"找到 {len(pdf_files)} 个 PDF 文件")
    
    # 构建任务列表
    tasks = []
    for pdf_path in pdf_files:
        output_path = get_output_path(pdf_path)
        if output_path is None:
            continue
        
        # 跳过已存在且大于 1KB 的文件
        if output_path.exists() and output_path.stat().st_size > 1000:
            continue
        
        tasks.append((pdf_path, output_path))
    
    logger.info(f"需要转换: {len(tasks)} 个文件")
    
    if not tasks:
        logger.info("所有文件已转换完成")
        return
    
    # 并行转换
    success = 0
    failed = 0
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(convert_single_pdf, task): task for task in tasks}
        
        for i, future in enumerate(as_completed(futures)):
            ok, path, info = future.result()
            if ok:
                success += 1
                logger.info(f"✓ [{i+1}/{len(tasks)}] {Path(path).name} ({info} chars)")
            else:
                failed += 1
                logger.error(f"✗ [{i+1}/{len(tasks)}] {path}: {info}")
    
    logger.info(f"转换完成: 成功 {success}, 失败 {failed}")

if __name__ == "__main__":
    batch_convert(max_workers=4)
