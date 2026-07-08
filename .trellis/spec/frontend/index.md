# 前端规范 - homework-pet v3.3

> **位置**: `app/templates/index.html` (Jinja2 单页)
> **行数**: ~3243 行

## 文件结构

单文件包含:
- HTML 结构
- CSS 样式 (内联 `<style>`)
- JavaScript 逻辑 (内联 `<script>`)

## v3.3 新增 UI 组件

### 1. 宠物卡片轮播
- 位置: 宠物展示区下方
- 横向滚动，每张卡片 80px 宽
- 激活宠物高亮 (紫色边框)
- 左右滑动按钮

### 2. 领养中心弹窗
- 7 种物种网格展示
- 已领养标记 ✅
- 价格 + 领养按钮

### 3. 扭蛋机弹窗
- 普通/高级两个池
- 概率明示
- 抽取动画

## 现有 UI 风格

- 配色: 紫色主题 (#B388FF)
- 字体: 系统默认
- 圆角: 12px
- 卡片: 浅灰背景 #f5f5f5

## 关键 API 调用位置 (27 处)

```bash
# 列出所有 fetch 调用
grep -n "fetch('/api/" app/templates/index.html
```

主要调用:
- `/api/pet` → 改为 `/api/pets/active`
- `/api/pet/mood` → 保留 (后端已重构为读激活宠物)
- `/api/pet/feed`, `/api/pet/interact` → 保留路径 (后端已重构)
- `/api/pet/skins` → 保留路径 (后端已重构为按个体)
- `/api/task/complete` → 保留 (响应增加 newly_unlocked_achievements)
- `/api/pets/*` → 新增调用

## CSS 命名约定

- BEM 风格: `.pet-card__name`, `.pet-card--active`
- 状态类: `.active`, `.locked`, `.owned`
- 容器: `.pet-carousel`, `.carousel-track`, `.modal-content`

## JS 函数命名

- 加载: `loadXxx()` (如 `loadPetCarousel`)
- 显示弹窗: `showXxxModal()` 或 `showXxx()`
- 关闭弹窗: `closeModal(id)`
- 异步调用: `async function xxx()`
