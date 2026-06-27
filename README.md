# SpreadFleet（传播舰队）

社媒账号舰队管理与任务编排平台（**测试环境**）。

**Repository:** https://github.com/SpreadXAI/spread-fleet

- Frontend: Vue 3 + Vite + Tailwind（静态 + Nginx）
- Backend: FastAPI + PostgreSQL（`agent_ops_test` schema）
- Deploy: imjson ECS，路径 `/spreadfleet/`

## 线上访问

- http://118.31.57.25/spreadfleet/
- 旧路径 `/agent-ops/` 会自动跳转到新地址

## 本地开发

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export PYTHONPATH=.
uvicorn app.main:app --reload --port 9092

cd frontend && npm install && npm run dev
```

## 部署

```bash
python3 scripts/ecs-deploy.py
```

## E2E

```bash
cd frontend && npm ci && npx playwright install chromium
E2E_BASE_URL=http://118.31.57.25/spreadfleet npm run test:e2e
```
