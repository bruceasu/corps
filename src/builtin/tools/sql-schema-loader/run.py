import argparse
import os
import sys
from pathlib import Path

def add_runtime_path() -> None:
    scripts_dir = os.getenv("CORPS_PYTHON_SCRIPTS_DIR")
    if scripts_dir:
        runtime_dir = Path(scripts_dir).resolve() / "_runtime"
    else:
        runtime_dir = Path(__file__).resolve().parents[3] / "_runtime"
    sys.path.insert(0, str(runtime_dir))

add_runtime_path()

from tool_runtime import emit_result, failure, success

# 模拟数据库元数据存储。在实际项目中，这里可以对接真实的数据库 SHOW CREATE TABLE 或知识库。
# 对应文章中的 "Knowledge Index" 思想
MOCK_KNOWLEDGE_INDEX = {
    "users": """
Table: users
Columns:
  - id (int, PK): 用户唯一标识
  - username (varchar): 用户名
  - email (varchar): 邮箱
  - status (enum): 'active', 'inactive'
  - created_at (datetime): 注册时间
""",
    "orders": """
Table: orders
Columns:
  - id (int, PK): 订单唯一标识
  - user_id (int, FK references users.id): 关联用户
  - total_amount (decimal): 订单总金额
  - status (enum): 'pending', 'paid', 'shipped', 'cancelled'
  - created_at (datetime): 下单时间
""",
    "products": """
Table: products
Columns:
  - id (int, PK): 产品唯一标识
  - name (varchar): 产品名称
  - price (decimal): 单价
  - stock (int): 库存数量
"""
}

def main():
    parser = argparse.ArgumentParser(description="Load SQL schema metadata.")
    parser.add_argument("--tables", required=True, help="Comma separated table names")
    args = parser.parse_args()

    requested_tables = [t.strip() for t in args.tables.split(",") if t.strip()]
    
    result_text = "## Database Schema Metadata\n\n"
    found_any = False
    
    for table in requested_tables:
        if table in MOCK_KNOWLEDGE_INDEX:
            result_text += f"### {table}\n{MOCK_KNOWLEDGE_INDEX[table]}\n"
            found_any = True
        else:
            result_text += f"### {table}\nWarning: No metadata found for table '{table}'.\n"

    if not found_any:
        # 如果没找到特定的表，返回可用表列表
        result_text += "\nAvailable tables in knowledge index: " + ", ".join(MOCK_KNOWLEDGE_INDEX.keys())

    emit_result(success("sql-schema-loader", result_text, {
        "requested": requested_tables,
        "found": [t for t in requested_tables if t in MOCK_KNOWLEDGE_INDEX]
    }))

if __name__ == "__main__":
    main()
