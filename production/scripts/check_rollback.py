#!/usr/bin/env python3
"""
回滚检查脚本
检查回滚准备状态
"""

import sys
import os
import json
from datetime import datetime

def check_rollback_preparedness():
    """检查回滚准备状态"""
    checks = {}
    
    # 检查备份文件
    v17_path = r"C:\Users\Administrator\.openclaw\production\v1.7_final_backup\optimized_algorithm_v1_7_final.py"
    checks["backup_file"] = os.path.exists(v17_path)
    
    # 检查备份文件大小
    if checks["backup_file"]:
        file_size = os.path.getsize(v17_path)
        checks["backup_file_size"] = file_size > 1000  # 大于1KB
    else:
        checks["backup_file_size"] = False
    
    # 检查配置文件中的备份版本
    config_path = r"C:\Users\Administrator\.openclaw\production\config\production_config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            checks["config_backup_version"] = config.get("backup_version") == "V1.7_final_backup"
        except:
            checks["config_backup_version"] = False
    else:
        checks["config_backup_version"] = False
    
    return checks

def main():
    """主函数"""
    print("=" * 60)
    print("回滚检查脚本")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查回滚准备
    print("[INFO] 检查回滚准备状态...")
    checks = check_rollback_preparedness()
    
    all_ready = True
    for check_name, check_result in checks.items():
        if check_result:
            print(f"[OK] {check_name}: 就绪")
        else:
            print(f"[ERROR] {check_name}: 未就绪")
            all_ready = False
    
    # 保存检查结果
    try:
        result = {
            "timestamp": datetime.now().isoformat(),
            "checks": checks,
            "rollback_ready": all_ready
        }
        
        status_dir = r"C:\Users\Administrator\.openclaw\production\logs\status"
        os.makedirs(status_dir, exist_ok=True)
        
        report_file = os.path.join(status_dir, f"rollback_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] 检查结果已保存: {report_file}")
        
    except Exception as e:
        print(f"[ERROR] 保存检查结果失败: {e}")
    
    # 返回状态
    if all_ready:
        print("\n[SUCCESS] 回滚准备就绪")
        return 0
    else:
        print("\n[ERROR] 回滚准备未就绪")
        return 1

if __name__ == "__main__":
    sys.exit(main())
