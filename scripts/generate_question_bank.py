#!/usr/bin/env python3
"""
基础题库预生成脚本：读取 Markdown → LLM 出题 → 入库
每学科每年级每章节预生成 20 题
"""
import os
import sys
import json
import re
import time
import random
import logging
import asyncio
import httpx
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("question-bank-generator")

BASE_DIR = Path(__file__).resolve().parent.parent
MARKDOWN_DIR = BASE_DIR / "docs" / "教材" / "markdown"

# Hermes API 配置
HERMES_API_URL = os.getenv("HERMES_API_URL", "")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
HERMES_TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "120"))

# 出题 System Prompt
SYSTEM_PROMPT = """你是一名专业的小学教育命题专家。
你的任务是根据中国小学课程标准，生成适合小学1-5年级学生的练习题。

你必须：
1. 严格控制知识范围，不超纲
2. 控制题目难度，适合对应年级
3. 使用儿童容易理解的语言
4. 保证答案唯一正确
5. 提供详细解析

禁止：
1. 如果无法确定答案，不要生成
2. 不要编造教材内容
3. 不要引用不存在的资料
4. 不要生成多个正确答案
5. 不要出现超纲知识"""

def call_hermes(messages, temperature=0.3):
    """调用 Hermes API"""
    if not HERMES_API_URL:
        logger.warning("HERMES_API_URL 未配置，跳过")
        return None
    
    headers = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {HERMES_API_KEY}"
    
    payload = {
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    
    try:
        resp = httpx.post(HERMES_API_URL, json=payload, headers=headers, timeout=float(HERMES_TIMEOUT))
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Hermes API 调用失败: {e}")
        return None

def generate_questions_for_chapter(subject, grade, chapter_name, chapter_content, count=20):
    """为单个章节生成题目"""
    subject_name = {"chinese": "语文", "math": "数学", "english": "英语"}.get(subject, subject)
    
    # 截取内容（避免超长）
    content_snippet = chapter_content[:3000]
    
    user_prompt = f"""请根据以下教材内容生成{count}道小学{grade}年级{subject_name}选择题。

【教材参考】
{content_snippet}

【知识点】{chapter_name}
【难度分布】简单{int(count*0.5)}题 + 中等{int(count*0.3)}题 + 挑战{count - int(count*0.5) - int(count*0.3)}题
【输出格式】严格输出JSON数组：
[{{"question":"题目内容","options":["A.选项1","B.选项2","C.选项3","D.选项4"],"answer":"A","analysis":"详细解析","knowledge_point":"知识点名称"}}]"""
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    
    result = call_hermes(messages)
    if not result:
        return []
    
    # 解析 JSON
    try:
        result = result.strip()
        if result.startswith("```"):
            parts = result.split("```")
            result = parts[1] if len(parts) > 1 else result
            if result.startswith("json"):
                result = result[4:]
        result = result.strip()
        
        questions = json.loads(result)
        
        # 校验和清洗
        valid_questions = []
        for q in questions:
            if not q.get('question') or len(q.get('options', [])) != 4:
                continue
            if q.get('answer', '') not in ['A', 'B', 'C', 'D']:
                continue
            valid_questions.append({
                'question_text': q['question'],
                'options': q['options'],
                'correct_answer': q['answer'],
                'explanation': q.get('analysis', q.get('explanation', '')),
                'knowledge_point': q.get('knowledge_point', chapter_name),
            })
        
        return valid_questions[:count]
    except Exception as e:
        logger.error(f"解析题目失败: {e}")
        return []

def batch_generate_question_bank():
    """批量生成基础题库"""
    if not MARKDOWN_DIR.exists():
        logger.error(f"Markdown 目录不存在: {MARKDOWN_DIR}")
        return
    
    # 连接数据库
    sys.path.insert(0, str(BASE_DIR / "app"))
    from database import get_db_connection
    
    conn = get_db_connection()
    
    # 获取所有知识点
    kp_rows = conn.execute("SELECT * FROM knowledge_points ORDER BY subject, grade, sort_order").fetchall()
    
    if not kp_rows:
        logger.warning("知识图谱为空，请先生成知识图谱")
        conn.close()
        return
    
    total_generated = 0
    total_failed = 0
    
    for kp in kp_rows:
        kp = dict(kp)
        subject = kp['subject']
        grade = kp['grade']
        kp_id = kp['id']
        chapter = kp['chapter']
        
        # 检查是否已有足够题目
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM question_bank WHERE kp_id = ?", (kp_id,)
        ).fetchone()['cnt']
        
        if existing >= 20:
            logger.info(f"跳过(已有{existing}题): {kp_id}")
            continue
        
        # 读取 Markdown 内容
        source_tbk = kp.get("source_textbook") or ""
        md_path = MARKDOWN_DIR / subject / source_tbk / f"{grade}年级.md" if source_tbk else None
        if not md_path.exists():
            # 尝试其他路径
            md_files = list((MARKDOWN_DIR / subject).rglob(f"*{grade}*.md"))
            if md_files:
                md_path = md_files[0]
            else:
                logger.warning(f"找不到 Markdown: {kp_id}")
                total_failed += 1
                continue
        
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取章节内容
        chapter_content = extract_section(content, chapter)
        
        # 生成题目
        questions = generate_questions_for_chapter(subject, grade, chapter, chapter_content, 20)
        
        if not questions:
            total_failed += 1
            continue
        
        # 计算难度分布
        for i, q in enumerate(questions):
            if i < 5:
                difficulty = 1  # 简单
            elif i < 8:
                difficulty = 2  # 中等
            else:
                difficulty = 3  # 挑战
            
            conn.execute("""
                INSERT INTO question_bank
                (kp_id, subject, grade, chapter, difficulty, question_text, options, correct_answer, explanation, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                kp_id, subject, grade, chapter, difficulty,
                q['question_text'],
                json.dumps(q['options'], ensure_ascii=False),
                q['correct_answer'],
                q['explanation'],
                'textbook',
            ))
        
        conn.commit()
        total_generated += len(questions)
        logger.info(f"✓ {kp_id}: 生成 {len(questions)} 题")
        
        # 限流
        time.sleep(1)
    
    conn.close()
    logger.info(f"题库生成完成: 成功 {total_generated} 题, 失败 {total_failed}")

def extract_section(content, section_name):
    """从 Markdown 中提取指定章节内容"""
    lines = content.split('\n')
    in_section = False
    section_lines = []
    
    for line in lines:
        if line.startswith('## ') or line.startswith('### '):
            title = line.lstrip('#').strip()
            if section_name in title or title in section_name:
                in_section = True
                section_lines.append(line)
            elif in_section:
                break
        elif in_section:
            section_lines.append(line)
    
    return '\n'.join(section_lines) if section_lines else content[:3000]

if __name__ == "__main__":
    batch_generate_question_bank()

