#!/usr/bin/env python3
"""
简单监控脚本
检查系统基本状态
"""

import sys
import os
import json
from datetime import datetime

def check_system():
    """检查系统状态"""
    checks = {}
    
    # 检查算法文件
    v18_path = r"C:\Users\Administrator\.openclaw\production\v1.8_optimized\optimized_algorithm_v1_8_optimized.py"
    checks["v1.8_file"] = os.path.exists(v18_path)
    
    # 检查备份文件
    v17_path = r"C:\Users\Administrator\.openclaw\production\v1.7_final_backup\optimized_algorithm_v1_7_final.py"
    checks["v1.7_file"] = os.path.exists(v17_path)
    
    # 检查配置文件
    config_path = r"C:\Users\Administrator\.openclaw\production\config\production_config.json"
    checks["config_file"] = os.path.exists(config_path)
    
    # 检查数据目录
    data_path = r"C:\Users\Administrator\.openclaw\production\data"
    checks["data_dir"] = os.path.exists(data_path)
    
    # 检查日志目录
    logs_path = r"C:\Users\Administrator\.openclaw\production\logs"
    checks["logs_dir"] = os.path.exists(logs_path)
    
    return checks

def main():
    """主函数"""
    print("=" * 60)
    print("简单监控脚本")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查系统状态
    print("[INFO] 检查系统状态...")
    checks = check_system()
    
    all_ok = True
    for check_name, check_result in checks.items():
        if check_result:
            print(f"[OK] {check_name}: 正常")
        else:
            print(f"[ERROR] {check_name}: 异常")
            all_ok = False
    
    # 保存检查结果
    try:
        result = {
            "timestamp": datetime.now().isoformat(),
            "checks": checks,
            "all_ok": all_ok
        }
        
        status_dir = r"C:\Users\Administrator\.openclaw\production\logs\status"
        os.makedirs(status_dir, exist_ok=True)
        
        report_file = os.path.join(status_dir, f"monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] 检查结果已保存: {report_file}")
        
    except Exception as e:
        print(f"[ERROR] 保存检查结果失败: {e}")
    
    # 返回状态
    if all_ok:
        print("\n[SUCCESS] 所有检查通过")
        return 0
    else:
        print("\n[ERROR] 发现异常")
        return 1

if __name__ == "__main__":
    sys.exit(main())
