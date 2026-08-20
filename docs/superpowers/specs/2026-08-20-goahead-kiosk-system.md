# Go-Ahead Singapore Bus Interchange Kiosk — System Spec

> Saved verbatim from the original request on 2026-08-20 so implementation plans can
> travel with the spec they implement. This is the full, multi-module vision; each
> module is implemented via its own plan in `docs/superpowers/plans/`.

针对 Go-Ahead Singapore 巴士转换站（Bus Interchange）的智能触控 Kiosk / 客服交互系统，整体架构与功能模块设计如下：

## 系统架构与首页布局

- **双语与无障碍切换**：顶部常驻中/英文（EN / 中文）一键切换，支持字体放大与语音朗读（TTS）辅助。
- **首页 4 大核心入口**：采用高对比度磁贴式卡片设计，便于快速触控选择。

| 模块名称 | 核心定位 | 关键交互 |
| --- | --- | --- |
| 1. 路线指引 (Wayfinding) | 核心高频功能 | 虚拟键盘输入 / 热门地标一键选择 / 语音输入 |
| 2. 失物招领 (Lost & Found) | 事务登记与查询 | 自助登记报失 / 历史拾获公示检索 |
| 3. 意见反馈 (Feedback) | 运营满意度与投诉 | 满意度打分 / 分类问题提交（附车牌/路线号） |
| 4. 周边探索 (Explore Nearby) | 社区与商业导览 | 分类地标推荐 / 步行导航与商场地库指引 |

## 核心功能详细设计

### 1. 智能寻路与乘车指引 (Bus Wayfinding)

- **查询方式**：支持输入邮编（6位 Postal Code）、建筑名、地标、地铁站或巴士站编码；提供"热门直达"快捷按钮（如附近综合医院、商场、政府机构、樟宜机场等）。
- **结果展示卡片**：
  - **候车位置**：明确提示目标 **Berth / 泊位编号**（如 *Berth 3*）并配有站内平面图高亮动线。
  - **乘车方案**：推荐巴士路线（如 *Bus 83, 118, 382G*），标明直达或转乘方案。
  - **实时动态**：对接 LTA DataMall API，实时显示下一班及再下一班巴士的 **预计到达时间（ETA）** 及拥挤度（Green/Amber/Red）。
  - **行程耗时**：预估车程时间与总停靠站数（例：*15 mins, 6 stops*）。
  - **便携带走**：生成动态 QR 码，乘客手机扫码即可带走路线规划。

### 2. 失物招领 (Lost & Found)

- **报失登记**：乘客触控选择遗失物品分类（钱包/手机/证件/雨伞等）、遗失时间段、可能遗失的巴士线路或站内区域，留下联系电话（支持本地/海外号码）。
- **公示检索**：展示近期站点控制中心（Interchange Office）已登记的待认领物品列表（隐藏敏感信息）。
- **值班联络**：一键呼叫站内控制台或显示办公柜台指引路线。

### 3. 意见与建议 (Feedback & Service Rating)

- **轻量化评价**：5星/表情打分（车厢整洁度、车长服务、站内设施、准点率）。
- **事件上报**：可输入具体巴士车牌（如 *SG5000X*）、线路号及事发时间，提交至 Go-Ahead 运营后台。
- **快速回执**：提交后生成工单编号（Ref No.），扫码同步至手机追踪处理进度。

### 4. 附近兴趣点 (Nearby Places of Interest)

- **分类导航**：美食与商场（Shopping Mall、Hawker Centre）；公共便民（洗手间、ATM、母婴室、MRT 换乘口、自行车站）；医疗与社区（Polyclinic、Community Centre）。
- **出行动线**：提供出站步行距离、耗时及无障碍通道（坡道/电梯）指引。

## 技术对接与硬件建议

- **API 对接**：集成 LTA DataMall（实时 Bus Arrival、Bus Routes、Services 数据）及 OneMap API（新加坡本地高精度地理编码与步行寻路）。
- **硬件规格**：32/43 英寸工业级防眩光触控屏（防泼溅、支持全天候 24/7 运行），配备热敏打印机（用于打印路线小票/工单）与二维码扫码器。
- **离线容灾**：保留本地站内静态 Berth 映射与主干线路缓存，遇网络波动时保障基础寻路不中断。

## Planning decisions made when scoping this spec (2026-08-20)

These were resolved with the project owner before writing implementation plans:

1. **Split into one plan per module.** This spec covers 4 largely independent
   subsystems plus a shared shell; each gets its own plan under
   `docs/superpowers/plans/`, starting with the Kiosk Shell.
2. **First plan: Kiosk Shell** (home screen with the 4 tiles + bilingual/accessibility
   controls). The other three module plans (Lost & Found, Feedback, Nearby POI) build
   on top of the shell's view-routing and i18n modules.
3. **Persistence for Lost & Found / Feedback:** SQLite via FastAPI (the existing
   backend has no database — it only reads static JSON files and calls live external
   APIs). To be introduced in those modules' own plans.
4. **Hardware section (32/43" screen, thermal printer, QR scanner, offline cache):**
   out of scope for code plans except the software-side integration points — QR code
   generation (image/data URI) and printable HTML receipts via `window.print()`.
   Physical printer/scanner drivers and device provisioning are deployment concerns,
   not implementation tasks.
