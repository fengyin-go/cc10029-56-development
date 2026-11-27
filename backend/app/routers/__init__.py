"""业务路由汇总：所有模块共用一套资源路由，由领域服务完成分派。"""
from __future__ import annotations

from app.routers import evidence, resource

# 证据凭证路由含固定前缀 /api/evidence，须排在通用动态路由 /api/{module} 之前。
ROUTERS = [evidence, resource]
