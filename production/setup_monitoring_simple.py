#!/usr/bin/env python3
"""
监控设置脚本 - 简化版
设置基础监控配置
"""

import sys
import os
import json
from datetime import datetime

def create_monitoring_config():
    """创建监控配置文件"""
    print("[INFO] 创建监控配置文件...")
    
    try:
        config_path = r"C:\Users\Administrator\.openclaw\production\config\monitoring_config.json"
        
        monitoring_config = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "monitoring_enabled": True,
            "monitoring_interval_minutes": 5,
            "alert_channels": ["log", "file"],
            "thresholds": {
                "accuracy": {
                    "warning": 0.95,
                    "critical": 0.90,
                    "check_interval": 300
                },
                "score_error": {
                    "warning": 10.0,
                    "critical": 15.0,
                    "check_interval": 300
                },
                "communication_recognition": {
                    "warning": 0.90,
                    "critical": 0.85,
                    "check_interval": 300
                },
                "response_time": {
                    "warning": 2000,
                    "critical": 5000,
                    "check_interval": 60
                },
                "error_rate": {
                    "warning": 0.05,
                    "critical": 0.10,
                    "check_interval": 300
                }
            },
            "log_settings": {
                "log_level": "INFO",
                "max_log_size_mb": 100,
                "log_retention_days": 30
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(monitoring_config, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] 监控配置文件创建成功: {config_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建监控配置文件失败: {e}")
        return False

def create_log_directories():
    """创建日志目录结构"""
    print("\n[INFO] 创建日志目录结构...")
    
    try:
        log_dirs = [
            r"C:\Users\Administrator\.openclaw\production\logs\monitoring",
            r"C:\Users\Administrator\.openclaw\production\logs\performance",
            r"C:\Users\Administrator\.openclaw\production\logs\errors",
            r"C:\Users\Administrator\.openclaw\production\logs\status"
        ]
        
        for log_dir in log_dirs:
            os.makedirs(log_dir, exist_ok=True)
            print(f"[OK] 创建日志目录: {log_dir}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建日志目录失败: {e}")
        return False

def create_basic_monitor_script():
    """创建基础监控脚本"""
    print("\n[INFO] 创建基础监控脚本...")
    
    try:
        scripts_dir = r"C:\Users\Administrator\.openclaw\production\scripts"
        os.makedirs(scripts_dir, exist_ok=True)
        
        # 创建简单监控脚本
        monitor_script = os.path.join(scripts_dir, "simple_monitor.py")
        script_content = '''#!/usr/bin/env python3
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
    v18_path = r"C:\\Users\\Administrator\\.openclaw\\production\\v1.8_optimized\\optimized_algorithm_v1_8_optimized.py"
    checks["v1.8_file"] = os.path.exists(v18_path)
    
    # 检查备份文件
    v17_path = r"C:\\Users\\Administrator\\.openclaw\\production\\v1.7_final_backup\\optimized_algorithm_v1_7_final.py"
    checks["v1.7_file"] = os.path.exists(v17_path)
    
    # 检查配置文件
    config_path = r"C:\\Users\\Administrator\\.openclaw\\production\\config\\production_config.json"
    checks["config_file"] = os.path.exists(config_path)
    
    # 检查数据目录
    data_path = r"C:\\Users\\Administrator\\.openclaw\\production\\data"
    checks["data_dir"] = os.path.exists(data_path)
    
    # 检查日志目录
    logs_path = r"C:\\Users\\Administrator\\.openclaw\\production\\logs"
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
        
        status_dir = r"C:\\Users\\Administrator\\.openclaw\\production\\logs\\status"
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
'''
        
        with open(monitor_script, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"[OK] 创建监控脚本: {monitor_script}")
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建监控脚本失败: {e}")
        return False

def create_rollback_check_script():
    """创建回滚检查脚本"""
    print("\n[INFO] 创建回滚检查脚本...")
    
    try:
        scripts_dir = r"C:\Users\Administrator\.openclaw\production\scripts"
        check_script = os.path.join(scripts_dir, "check_rollback.py")
        
        script_content = '''#!/usr/bin/env python3
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
    v17_path = r"C:\\Users\\Administrator\\.openclaw\\production\\v1.7_final_backup\\optimized_algorithm_v1_7_final.py"
    checks["backup_file"] = os.path.exists(v17_path)
    
    # 检查备份文件大小
    if checks["backup_file"]:
        file_size = os.path.getsize(v17_path)
        checks["backup_file_size"] = file_size > 1000  # 大于1KB
    else:
        checks["backup_file_size"] = False
    
    # 检查配置文件中的备份版本
    config_path = r"C:\\Users\\Administrator\\.openclaw\\production\\config\\production_config.json"
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
        
        status_dir = r"C:\\Users\\Administrator\\.openclaw\\production\\logs\\status"
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
'''
        
        with open(check_script, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"[OK] 创建回滚检查脚本: {check_script}")
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建回滚检查脚本失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("监控设置工具 - 简化版")
    print(f"设置时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 执行设置步骤
    steps = [
        ("创建监控配置文件", create_monitoring_config),
        ("创建日志目录结构", create_log_directories),
        ("创建基础监控脚本", create_basic_monitor_script),
        ("创建回滚检查脚本", create_rollback_check_script)
    ]
    
    results = []
    
    for step_name, step_func in steps:
        print(f"\n[步骤] {step_name}")
        success = step_func()
        results.append((step_name, success))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("监控设置结果汇总:")
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
        print("\n[成功] 监控设置完成！")
        print("\n已设置:")
        print("1. [OK] 监控配置文件")
        print("2. [OK] 日志目录结构")
        print("3. [OK] 基础监控脚本")
        print("4. [OK] 回滚检查脚本")
        return 0
    else:
        print(f"\n[警告] 有{total-passed}个步骤失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())