#!/usr/bin/env python3
"""
部署验证工具
用于验证V1.8_optimized部署的完整性和性能
"""

import sys
import os
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path

def check_file_integrity():
    """检查文件完整性"""
    print("🔍 检查文件完整性...")
    
    files_to_check = [
        {
            "path": r"C:\Users\Administrator\.openclaw\production\v1.8_optimized\optimized_algorithm_v1_8_optimized.py",
            "name": "V1.8_optimized主文件"
        },
        {
            "path": r"C:\Users\Administrator\.openclaw\production\v1.7_final_backup\optimized_algorithm_v1_7_final.py",
            "name": "V1.7_final_backup备份文件"
        },
        {
            "path": r"C:\Users\Administrator\.openclaw\production\config\production_config.json",
            "name": "生产配置文件"
        },
        {
            "path": r"C:\Users\Administrator\.openclaw\production\config\.env",
            "name": "环境变量文件"
        }
    ]
    
    all_valid = True
    
    for file_info in files_to_check:
        file_path = file_info["path"]
        file_name = file_info["name"]
        
        if os.path.exists(file_path):
            # 计算文件大小
            file_size = os.path.getsize(file_path)
            
            # 计算MD5哈希
            try:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()[:8]
            except Exception as e:
                file_hash = f"错误: {e}"
            
            print(f"  [OK] {file_name}: 存在, 大小: {file_size}字节, MD5: {file_hash}")
        else:
            print(f"  [ERROR] {file_name}: 文件不存在")
            all_valid = False
    
    return all_valid

def check_directory_structure():
    """检查目录结构"""
    print("\n🔍 检查目录结构...")
    
    directories_to_check = [
        r"C:\Users\Administrator\.openclaw\production",
        r"C:\Users\Administrator\.openclaw\production\v1.8_optimized",
        r"C:\Users\Administrator\.openclaw\production\v1.7_final_backup",
        r"C:\Users\Administrator\.openclaw\production\data",
        r"C:\Users\Administrator\.openclaw\production\logs",
        r"C:\Users\Administrator\.openclaw\production\config"
    ]
    
    all_valid = True
    
    for dir_path in directories_to_check:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            print(f"  ✅ 目录存在: {dir_path}")
        else:
            print(f"  ❌ 目录不存在: {dir_path}")
            all_valid = False
    
    return all_valid

def check_dependencies():
    """检查依赖"""
    print("\n🔍 检查Python依赖...")
    
    required_packages = [
        "chromadb",
        "numpy",
        "json",
        "re",
        "datetime"
    ]
    
    all_installed = True
    
    for package in required_packages:
        try:
            if package == "json":
                import json
            elif package == "re":
                import re
            elif package == "datetime":
                import datetime
            else:
                __import__(package)
            print(f"  ✅ {package}: 已安装")
        except ImportError:
            print(f"  ❌ {package}: 未安装")
            all_installed = False
    
    return all_installed

def check_configuration():
    """检查配置"""
    print("\n🔍 检查配置文件...")
    
    config_path = r"C:\Users\Administrator\.openclaw\production\config\production_config.json"
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 检查必要配置项
        required_keys = ["version", "deployment_time", "backup_version", "performance_targets", "rollback_conditions"]
        
        all_valid = True
        for key in required_keys:
            if key in config:
                print(f"  ✅ 配置项 '{key}': 存在")
            else:
                print(f"  ❌ 配置项 '{key}': 缺失")
                all_valid = False
        
        # 检查性能目标
        if "performance_targets" in config:
            targets = config["performance_targets"]
            print(f"  📊 性能目标:")
            print(f"    准确率: ≥{targets.get('accuracy', 'N/A')}")
            print(f"    评分误差: <{targets.get('score_error', 'N/A')}分")
            print(f"    communication识别: ≥{targets.get('communication_recognition', 'N/A')}")
            print(f"    响应时间: <{targets.get('response_time', 'N/A')}秒")
        
        return all_valid
        
    except Exception as e:
        print(f"  ❌ 配置文件检查失败: {e}")
        return False

def check_version_consistency():
    """检查版本一致性"""
    print("\n🔍 检查版本一致性...")
    
    try:
        # 读取配置文件中的版本
        config_path = r"C:\Users\Administrator\.openclaw\production\config\production_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        config_version = config.get("version", "")
        backup_version = config.get("backup_version", "")
        
        print(f"  📋 配置版本: {config_version}")
        print(f"  📋 备份版本: {backup_version}")
        
        # 检查版本文件是否存在
        v18_path = r"C:\Users\Administrator\.openclaw\production\v1.8_optimized\optimized_algorithm_v1_8_optimized.py"
        v17_path = r"C:\Users\Administrator\.openclaw\production\v1.7_final_backup\optimized_algorithm_v1_7_final.py"
        
        v18_exists = os.path.exists(v18_path)
        v17_exists = os.path.exists(v17_path)
        
        print(f"  📁 V1.8_optimized文件: {'✅ 存在' if v18_exists else '❌ 缺失'}")
        print(f"  📁 V1.7_final_backup文件: {'✅ 存在' if v17_exists else '❌ 缺失'}")
        
        return v18_exists and v17_exists
        
    except Exception as e:
        print(f"  ❌ 版本一致性检查失败: {e}")
        return False

def generate_deployment_report():
    """生成部署报告"""
    print("\n📋 生成部署报告...")
    
    report = {
        "deployment_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "V1.8_optimized",
        "backup_version": "V1.7_final_backup",
        "checks": {
            "file_integrity": check_file_integrity(),
            "directory_structure": check_directory_structure(),
            "dependencies": check_dependencies(),
            "configuration": check_configuration(),
            "version_consistency": check_version_consistency()
        },
        "system_info": {
            "python_version": sys.version,
            "platform": sys.platform,
            "working_directory": os.getcwd()
        }
    }
    
    # 保存报告
    report_path = r"C:\Users\Administrator\.openclaw\production\deployment_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ 部署报告已保存: {report_path}")
    
    return report

def main():
    """主函数"""
    print("=" * 60)
    print("生产环境部署验证工具")
    print(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 执行所有检查
    checks = [
        ("文件完整性", check_file_integrity),
        ("目录结构", check_directory_structure),
        ("Python依赖", check_dependencies),
        ("配置文件", check_configuration),
        ("版本一致性", check_version_consistency)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        print(f"\n[检查] {check_name}")
        success = check_func()
        results.append((check_name, success))
    
    # 生成部署报告
    report = generate_deployment_report()
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("验证结果汇总:")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for check_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{check_name}: {status}")
        if success:
            passed += 1
    
    print(f"\n📊 通过率: {passed}/{total} ({passed/total:.1%})")
    
    if passed == total:
        print("\n🎉 所有验证通过！部署完整性验证成功！")
        print("\n下一步:")
        print("1. 运行测试脚本: python test_production.py")
        print("2. 初始化数据存储")
        print("3. 启动监控服务")
        return 0
    else:
        print(f"\n⚠️  有{total-passed}个验证失败，请修复问题后重新部署")
        return 1

if __name__ == "__main__":
    sys.exit(main())