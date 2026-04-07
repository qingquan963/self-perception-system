#!/usr/bin/env python3
"""
数据存储初始化脚本
初始化ChromaDB向量存储和基础记忆数据
"""

import sys
import os
import json
import chromadb
from datetime import datetime
from pathlib import Path

def init_chromadb():
    """初始化ChromaDB向量存储"""
    print("[INFO] 初始化ChromaDB向量存储...")
    
    try:
        # 设置ChromaDB路径
        chroma_path = r"C:\Users\Administrator\.openclaw\production\data\chroma"
        
        # 创建目录
        os.makedirs(chroma_path, exist_ok=True)
        
        # 初始化ChromaDB客户端
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        
        # 创建集合（如果不存在）
        collection_name = "memory_vectors"
        try:
            collection = chroma_client.get_collection(name=collection_name)
            print(f"[INFO] 集合 '{collection_name}' 已存在，包含 {collection.count()} 个文档")
        except:
            collection = chroma_client.create_collection(name=collection_name)
            print(f"[INFO] 创建新集合 '{collection_name}'")
        
        # 测试集合
        test_documents = ["测试文档1: 系统初始化完成"]
        test_metadatas = [{"type": "system", "timestamp": datetime.now().isoformat()}]
        test_ids = ["test_doc_1"]
        
        collection.add(
            documents=test_documents,
            metadatas=test_metadatas,
            ids=test_ids
        )
        
        # 验证添加
        count = collection.count()
        print(f"[OK] ChromaDB初始化成功，当前文档数: {count}")
        
        return chroma_client, collection
        
    except Exception as e:
        print(f"[ERROR] ChromaDB初始化失败: {e}")
        return None, None

def init_memory_data():
    """初始化基础记忆数据"""
    print("\n[INFO] 初始化基础记忆数据...")
    
    try:
        memory_path = r"C:\Users\Administrator\.openclaw\production\data\memory"
        os.makedirs(memory_path, exist_ok=True)
        
        # 创建基础记忆数据
        base_memories = [
            {
                "id": "memory_001",
                "text": "系统初始化完成，V1.8_optimized版本部署成功",
                "type": "system",
                "score": 100.0,
                "timestamp": datetime.now().isoformat(),
                "version": "V1.8_optimized"
            },
            {
                "id": "memory_002",
                "text": "部署时间: 2026-03-23 20:28:00，版本: V1.8_optimized，备份版本: V1.7_final_backup",
                "type": "system",
                "score": 95.0,
                "timestamp": datetime.now().isoformat(),
                "version": "V1.8_optimized"
            },
            {
                "id": "memory_003",
                "text": "性能目标: 准确率≥95%，评分误差<10分，communication识别≥90%，响应时间<2秒",
                "type": "technical",
                "score": 90.0,
                "timestamp": datetime.now().isoformat(),
                "version": "V1.8_optimized"
            }
        ]
        
        # 保存记忆数据
        memory_file = os.path.join(memory_path, "base_memories.json")
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump(base_memories, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] 基础记忆数据初始化成功，保存到: {memory_file}")
        print(f"[INFO] 创建了 {len(base_memories)} 条基础记忆")
        
        return base_memories
        
    except Exception as e:
        print(f"[ERROR] 记忆数据初始化失败: {e}")
        return None

def create_data_structure():
    """创建完整的数据目录结构"""
    print("\n[INFO] 创建数据目录结构...")
    
    data_dirs = [
        r"C:\Users\Administrator\.openclaw\production\data\chroma",
        r"C:\Users\Administrator\.openclaw\production\data\memory",
        r"C:\Users\Administrator\.openclaw\production\data\backup",
        r"C:\Users\Administrator\.openclaw\production\data\temp",
        r"C:\Users\Administrator\.openclaw\production\data\logs"
    ]
    
    for dir_path in data_dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"[OK] 创建目录: {dir_path}")
    
    return True

def create_data_config():
    """创建数据配置文件"""
    print("\n[INFO] 创建数据配置文件...")
    
    try:
        config_path = r"C:\Users\Administrator\.openclaw\production\data\data_config.json"
        
        data_config = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "storage": {
                "chromadb_path": r"C:\Users\Administrator\.openclaw\production\data\chroma",
                "memory_data_path": r"C:\Users\Administrator\.openclaw\production\data\memory",
                "backup_path": r"C:\Users\Administrator\.openclaw\production\data\backup",
                "temp_path": r"C:\Users\Administrator\.openclaw\production\data\temp"
            },
            "collections": {
                "memory_vectors": "记忆向量存储",
                "keywords": "关键词索引",
                "analytics": "分析结果"
            },
            "backup_schedule": {
                "daily": True,
                "weekly": True,
                "monthly": True
            },
            "retention_policy": {
                "memory_data_days": 365,
                "vector_data_days": 180,
                "log_data_days": 30
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data_config, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] 数据配置文件创建成功: {config_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建数据配置文件失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("数据存储初始化工具")
    print(f"初始化时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 执行初始化步骤
    steps = [
        ("创建数据目录结构", create_data_structure),
        ("初始化ChromaDB向量存储", init_chromadb),
        ("初始化基础记忆数据", init_memory_data),
        ("创建数据配置文件", create_data_config)
    ]
    
    results = []
    
    for step_name, step_func in steps:
        print(f"\n[步骤] {step_name}")
        success = step_func()
        results.append((step_name, success))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("初始化结果汇总:")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for step_name, success in results:
        status = "[OK] 成功" if success else "[ERROR] 失败"
        print(f"{step_name}: {status}")
        if success:
            passed += 1
    
    print(f"\n[统计] 成功率: {passed}/{total} ({passed/total:.1%})")
    
    if passed == total:
        print("\n[成功] 数据存储初始化完成！")
        print("\n[数据存储状态]:")
        print("1. [OK] 目录结构创建完成")
        print("2. [OK] ChromaDB向量存储初始化完成")
        print("3. [OK] 基础记忆数据导入完成")
        print("4. [OK] 数据配置文件创建完成")
        return 0
    else:
        print(f"\n[警告] 有{total-passed}个步骤失败，请检查数据存储")
        return 1

if __name__ == "__main__":
    sys.exit(main())