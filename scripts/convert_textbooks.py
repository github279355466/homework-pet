#!/usr/bin/env python3
"""
教材处理脚本：PDF → Markdown → 知识图谱 → 基础题库
"""
import os
import sys
import json
import re
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("textbook-processor")

BASE_DIR = Path(__file__).resolve().parent.parent
TEXTBOOK_DIR = BASE_DIR / "docs" / "教材"
MARKDOWN_DIR = TEXTBOOK_DIR / "markdown"

# 学科映射
SUBJECT_MAP = {
    "小学语文": "chinese",
    "小学数学": "math",
    "小学英语": "english",
}

def convert_pdf_to_markdown(pdf_path, output_path):
    """使用 markitdown 将 PDF 转为 Markdown"""
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(str(pdf_path))
        content = result.text_content
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"✓ 转换完成: {pdf_path.name} -> {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"✗ 转换失败: {pdf_path.name} - {e}")
        return False

def batch_convert_textbooks():
    """批量转换所有教材 PDF"""
    pdf_files = list(TEXTBOOK_DIR.rglob("*.pdf"))
    logger.info(f"找到 {len(pdf_files)} 个 PDF 文件")
    
    success = 0
    failed = 0
    
    for pdf_path in pdf_files:
        # 构建输出路径: markdown/{学科}/{版本}/{年级}.md
        parts = pdf_path.relative_to(TEXTBOOK_DIR).parts
        if len(parts) < 2:
            continue
        
        subject_version = parts[0]  # 如 "小学语文-统编版"
        filename = parts[-1]  # 如 "义务教育教科书·语文一年级上册.pdf"
        
        # 提取学科和版本
        subject_key = None
        for key in SUBJECT_MAP:
            if subject_version.startswith(key):
                subject_key = SUBJECT_MAP[key]
                version = subject_version[len(key)+1:]  # 去掉学科前缀
                break
        
        if not subject_key:
            continue
        
        # 提取年级
        grade = extract_grade(filename)
        
        # 输出路径
        output_path = MARKDOWN_DIR / subject_key / version / f"{grade}年级.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_path.exists() and output_path.stat().st_size > 1000:
            logger.info(f"跳过(已存在): {output_path}")
            success += 1
            continue
        
        if convert_pdf_to_markdown(pdf_path, output_path):
            success += 1
        else:
            failed += 1
        
        # 避免 API 限流
        time.sleep(0.5)
    
    logger.info(f"转换完成: 成功 {success}, 失败 {failed}")
    return success, failed

def extract_grade(filename):
    """从文件名提取年级"""
    grade_map = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
        "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    }
    # 匹配 "一年级" 或 "1年级"
    for cn, num in [("一", 1), ("二", 2), ("三", 3), ("四", 4), ("五", 5), ("六", 6)]:
        if f"{cn}年级" in filename:
            return num
    # 匹配数字
    m = re.search(r'(\d+)年级', filename)
    if m:
        return int(m.group(1))
    return 1  # 默认1年级

def generate_knowledge_graph():
    """从 Markdown 文件生成知识图谱"""
    logger.info("开始生成知识图谱...")
    
    kp_list = []
    
    for md_file in MARKDOWN_DIR.rglob("*.md"):
        # 解析路径: markdown/{学科}/{版本}/{年级}.md
        parts = md_file.relative_to(MARKDOWN_DIR).parts
        if len(parts) < 3:
            continue
        
        subject = parts[0]
        version = parts[1]
        grade = int(parts[2].replace("年级.md", ""))
        
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取章节和知识点
        chapters = extract_chapters(content)
        
        for ch_idx, (chapter_name, ch_content) in enumerate(chapters):
            # 从章节内容中提取知识点
            knowledge_points = extract_knowledge_points(ch_content, subject)
            
            for kp_idx, kp_name in enumerate(knowledge_points):
                kp_id = f"kp_{subject}_g{grade}_ch{ch_idx:02d}_{kp_idx:03d}"
                kp_list.append({
                    "id": kp_id,
                    "subject": subject,
                    "grade": grade,
                    "chapter": chapter_name,
                    "name": kp_name,
                    "difficulty": min(5, 1 + kp_idx // 3),
                    "prerequisite": [],
                    "next": [],
                    "skills": json.dumps(["理解", "应用"], ensure_ascii=False),
                    "source_textbook": version,
                    "sort_order": ch_idx * 100 + kp_idx,
                })
    
    logger.info(f"生成知识图谱: {len(kp_list)} 个知识点")
    
    # 保存到 JSON
    kg_path = BASE_DIR / "docs" / "教材" / "knowledge_graph.json"
    with open(kg_path, 'w', encoding='utf-8') as f:
        json.dump(kp_list, f, ensure_ascii=False, indent=2)
    
    logger.info(f"知识图谱已保存: {kg_path}")
    return kp_list

def extract_chapters(content):
    """从 Markdown 内容提取章节"""
    chapters = []
    
    # 匹配 ## 或 ### 标题
    lines = content.split('\n')
    current_chapter = "综合"
    current_content = []
    
    for line in lines:
        if line.startswith('## '):
            if current_content:
                chapters.append((current_chapter, '\n'.join(current_content)))
            current_chapter = line[3:].strip()
            current_content = [line]
        elif line.startswith('### '):
            if current_content:
                chapters.append((current_chapter, '\n'.join(current_content)))
            current_chapter = line[4:].strip()
            current_content = [line]
        else:
            current_content.append(line)
    
    if current_content:
        chapters.append((current_chapter, '\n'.join(current_content)))
    
    # 如果没有提取到章节，按内容长度分段
    if len(chapters) <= 1 and len(content) > 500:
        # 按每 2000 字分段
        chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
        chapters = [(f"第{i+1}部分", chunk) for i, chunk in enumerate(chunks)]
    
    return chapters if chapters else [("综合", content)]

def extract_knowledge_points(chapter_content, subject):
    """从章节内容提取知识点"""
    points = []
    
    # 简单提取：按句子分割，取包含关键词的句子
    sentences = re.split(r'[。！？\n]', chapter_content)
    
    keywords = {
        "chinese": ["字", "词", "句", "段", "篇", "读", "写", "拼音", "成语", "古诗", "课文"],
        "math": ["数", "计算", "加减", "乘除", "分数", "小数", "图形", "面积", "周长", "应用题"],
        "english": ["单词", "句型", "对话", "阅读", "语法", "字母", "音标", "情景"],
    }
    
    subject_keywords = keywords.get(subject, [])
    
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 10 or len(sent) > 100:
            continue
        for kw in subject_keywords:
            if kw in sent and sent not in points:
                points.append(sent)
                break
    
    # 限制数量
    return points[:10] if points else [f"{subject}基础知识"]

def import_knowledge_graph_to_db():
    """将知识图谱导入数据库"""
    kg_path = BASE_DIR / "docs" / "教材" / "knowledge_graph.json"
    if not kg_path.exists():
        logger.error("知识图谱文件不存在，请先生成")
        return
    
    with open(kg_path, 'r', encoding='utf-8') as f:
        kp_list = json.load(f)
    
    # 连接数据库
    sys.path.insert(0, str(BASE_DIR / "app"))
    from database import get_db_connection
    
    conn = get_db_connection()
    for kp in kp_list:
        conn.execute("""
            INSERT OR REPLACE INTO knowledge_points
            (id, subject, grade, chapter, name, difficulty, prerequisite, next, skills, source_textbook, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            kp["id"], kp["subject"], kp["grade"], kp["chapter"],
            kp["name"], kp["difficulty"],
            json.dumps(kp.get("prerequisite", []), ensure_ascii=False),
            json.dumps(kp.get("next", []), ensure_ascii=False),
            kp.get("skills", "[]"),
            kp.get("source_textbook", ""),
            kp.get("sort_order", 0),
        ))
    conn.commit()
    conn.close()
    logger.info(f"导入知识图谱到数据库: {len(kp_list)} 条")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="教材处理脚本")
    parser.add_argument("action", choices=["convert", "kg", "import", "all"],
                       help="convert=PDF转Markdown, kg=生成知识图谱, import=导入数据库, all=全部")
    args = parser.parse_args()
    
    if args.action in ("convert", "all"):
        batch_convert_textbooks()
    
    if args.action in ("kg", "all"):
        generate_knowledge_graph()
    
    if args.action in ("import", "all"):
        import_knowledge_graph_to_db()
