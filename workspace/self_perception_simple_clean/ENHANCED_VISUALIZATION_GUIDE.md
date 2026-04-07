# 自我感知系统 - 增强数据可视化指南

## 概述

本文档介绍了自我感知系统的增强数据可视化功能，包括增强的API端点和前端仪表板。

## 系统架构

```
自我感知系统
├── 向量存储服务 (vector_service.py)
│   ├── 基础API端点
│   └── 增强API端点（新增）
└── 前端仪表板 (frontend/dashboard.html)
    ├── 数据可视化图表
    ├── 模块状态监控
    └── 实时数据更新
```

## 增强API端点

### 1. 详细统计API

#### GET `/stats/detailed`
返回详细的系统统计信息。

**响应示例：**
```json
{
  "stats": {
    "total": 30,
    "today_new": 30,
    "type_distribution": {
      "未知": 26,
      "conversation": 3,
      "test": 1
    },
    "vector_type_distribution": {
      "conversation": 25,
      "task": 4,
      "test": 1
    },
    "importance_distribution": {
      "1": 30
    },
    "weekly_trend": [
      {
        "date": "2026-03-28",
        "count": 30
      }
    ]
  },
  "timestamp": "2026-03-29T00:14:18.663286"
}
```

#### GET `/stats/by_type`
按类型分类统计。

#### GET `/stats/recent`
获取最近存储的数据。

### 2. 数据查询API

#### GET `/data/summary`
获取数据摘要信息。

#### GET `/data/files`
获取原始文件路径信息。

#### GET `/data/modules`
获取5个核心模块状态。

## 前端仪表板功能

### 1. 主要功能

- **实时数据监控**：每30秒自动更新数据
- **数据可视化**：使用Chart.js显示图表
- **模块状态监控**：5个核心模块实时状态
- **响应式设计**：适配不同屏幕尺寸
- **搜索功能**：支持数据表格搜索

### 2. 显示内容

#### 统计卡片
- 总存储量
- 今日新增
- 活跃模块数量
- 平均内容长度
- 数据时间范围

#### 核心模块状态
- 对话记忆模块
- 任务跟踪模块
- 决策记录模块
- 学习反馈模块
- 能力评估模块

#### 数据图表
- 类型分布饼图
- 最近7天存储趋势柱状图

#### 最近数据表格
- 显示最近存储的记录
- 支持搜索和筛选

## 部署指南

### 1. 启动向量服务

```bash
cd C:\Users\Administrator\.openclaw\workspace\self_perception_simple_clean
python vector_service.py
```

服务将在 `http://localhost:8007` 启动。

### 2. 访问前端仪表板

在浏览器中打开：
```
file:///C:/Users/Administrator/.openclaw/workspace/self_perception_simple_clean/frontend/dashboard.html
```

或通过HTTP服务器访问：
```bash
# 使用Python启动简单HTTP服务器
cd frontend
python -m http.server 8080
```

然后在浏览器中访问：`http://localhost:8080/dashboard.html`

### 3. 系统集成

#### 与现有系统集成
增强的API端点与现有系统完全兼容，不会影响现有功能。

#### 自动启动配置
可以修改现有的启动脚本，确保向量服务在系统启动时自动运行。

## 使用说明

### 1. 数据监控

1. 打开仪表板页面
2. 系统将自动加载数据
3. 数据每30秒自动更新
4. 点击模块卡片查看详细信息

### 2. 数据导出

1. 点击"导出数据"按钮（如果已添加）
2. 数据将以JSON格式下载
3. 包含所有统计信息和模块状态

### 3. 故障排除

#### 常见问题

1. **数据不更新**
   - 检查向量服务是否运行：`netstat -an | findstr :8007`
   - 检查浏览器控制台是否有错误

2. **图表不显示**
   - 检查网络连接
   - 确保Chart.js库正确加载

3. **API请求失败**
   - 检查CORS配置
   - 验证API端点URL

#### 日志查看

向量服务日志输出到控制台，包含：
- 服务启动信息
- API请求日志
- 错误信息

## 性能要求

### 1. 响应时间
- 页面加载时间：< 3秒
- 数据更新延迟：< 1秒
- API响应时间：< 500ms

### 2. 资源使用
- 内存使用：合理
- CPU使用：低
- 网络带宽：最小化

### 3. 兼容性
- 浏览器：Chrome 80+、Firefox 75+、Edge 80+
- 屏幕尺寸：桌面、平板、手机
- 操作系统：Windows、macOS、Linux

## 测试指南

### 1. API测试

运行测试脚本：
```bash
cd C:\Users\Administrator\.openclaw\workspace\self_perception_simple_clean
python test_enhanced_api.py
```

### 2. 前端测试

1. 手动测试所有功能
2. 测试响应式布局
3. 验证数据准确性
4. 测试错误处理

### 3. 集成测试

1. 测试与现有系统兼容性
2. 验证开机自动启动
3. 测试长时间运行稳定性

## 维护指南

### 1. 日常维护

- 监控服务运行状态
- 检查日志文件
- 定期备份数据

### 2. 故障恢复

1. **服务停止**
   ```bash
   # 重启服务
   taskkill /f /im python.exe
   python vector_service.py
   ```

2. **数据异常**
   - 检查数据库文件完整性
   - 恢复最近备份

### 3. 更新升级

1. 备份现有配置和数据
2. 更新代码文件
3. 重启服务
4. 验证功能正常

## 安全注意事项

### 1. 访问控制
- API服务默认监听所有接口（0.0.0.0）
- 生产环境建议配置防火墙规则
- 考虑添加身份验证

### 2. 数据安全
- 数据库文件存储在本地
- 定期备份重要数据
- 避免暴露敏感信息

### 3. 网络安全
- 使用HTTPS加密传输
- 配置适当的CORS策略
- 防止跨站脚本攻击

## 扩展开发

### 1. 添加新图表

1. 在HTML中添加canvas元素
2. 在JavaScript中初始化图表
3. 更新数据加载逻辑

### 2. 添加新API端点

1. 在vector_service.py中添加端点
2. 实现相应的数据查询方法
3. 更新前端数据加载

### 3. 自定义样式

1. 修改dashboard.css文件
2. 调整颜色和布局
3. 添加动画效果

## 技术支持

### 1. 文档资源
- API文档：`API_DOCUMENTATION.md`
- 用户手册：`USER_MANUAL.md`
- 开发者指南：`DEVELOPER_GUIDE.md`

### 2. 故障报告
- 查看系统日志
- 检查错误信息
- 联系技术支持

### 3. 更新通知
- 关注版本更新
- 阅读更新日志
- 及时升级系统

---

**版本：1.0.0**
**最后更新：2026-03-29**
**作者：数据可视化增强专家**