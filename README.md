# rag-agent-project

基于 RAG（检索增强生成）与多 Agent 架构的智能汽车服务助手，覆盖车况查询、车控、导航、故障诊断、预约、售后咨询等场景。

## 技术栈

- **后端**：Python 3.12 + FastAPI + LangChain + LangGraph
- **前端**：React 18 + TypeScript + Vite + Tailwind CSS + Zustand + React Flow
- **向量库**：ChromaDB
- **协议**：MCP（Model Context Protocol）
- **LLM**：通过 `model/factory.py` 工厂模式统一接入（兼容 OpenAI / 阿里云 DashScope 等）

## 目录结构

```
rag_agent_project/
├── agent/              # Agent 编排：多 Agent + ReAct
│   ├── multi_agent.py  # 主控编排器 + 6 个子 Agent
│   ├── react_agent.py  # ReAct 单 Agent
│   └── tools/          # Agent 工具与中间件
├── api/                # FastAPI 接口（WebSocket 流式对话）
├── config/             # 配置文件
├── data/               # 知识库手册（中文 6 份 + 高德 2 份）
├── frontend/           # React 前端
├── mcp_servers/        # MCP 服务（高德 / 车辆 / 导航 / 预约）
├── model/              # LLM 工厂
├── prompts/            # Prompt 模板
├── rag/                # RAG 检索 + 向量存储
├── utils/              # 工具函数
├── app.py              # 后端入口
├── requirements.txt
└── test_full.py        # 端到端测试
```

## 多 Agent 架构

```
Orchestrator (主控)
  │  意图识别 + 路由
  ▼
  ├── VehicleStatusAgent      车况查询
  ├── VehicleControlAgent     车控操作
  ├── NavigationAgent         导航服务
  ├── DiagnosisAgent          故障诊断
  ├── AppointmentAgent        预约服务
  └── CustomerServiceAgent    售后咨询
```

支持关键词预路由 + LLM 兜底分类、对话指代消解、导航意图预处理。

## 快速开始

### 后端
```bash
pip install -r requirements.txt
python app.py
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

## 配置

复制并按需修改 `config/*.yml`，并通过环境变量注入 API Key（**不要**将真实 Key 提交到仓库）。

## License

仅供学习交流。
