#!/usr/bin/env python3
"""
监控设置脚本
设置准确率监控、响应时间监控、错误率监控和自动告警
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

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
                    "check_interval": 300  # 5分钟
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
                    "warning": 2000,  # 2秒
                    "critical": 5000,  # 5秒
                    "check_interval": 60  # 1分钟
                },
                "error_rate": {
                    "warning": 0.05,  # 5%
                    "critical": 0.10,  # 10%
                    "check_interval": 300
                }
            },
            "alert_rules": {
                "immediate_alert": ["critical"],
                "delayed_alert": ["warning"],
                "notification_cooldown_minutes": 30
            },
            "log_settings": {
                "log_level": "INFO",
                "max_log_size_mb": 100,
                "log_retention_days": 30,
                "log_path": r"C:\Users\Administrator\.openclaw\production\logs"
            },
            "performance_history": {
                "retention_days": 7,
                "sampling_interval_minutes": 5
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
            r"C:\Users\Administrator\.openclaw\production\logs\audit"
        ]
        
        for log_dir in log_dirs:
            os.makedirs(log_dir, exist_ok=True)
            print(f"[OK] 创建日志目录: {log_dir}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建日志目录失败: {e}")
        return False

def create_alert_config():
    """创建告警配置文件"""
    print("\n[INFO] 创建告警配置文件...")
    
    try:
        alert_config_path = r"C:\Users\Administrator\.openclaw\production\config\alert_config.json"
        
        alert_config = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "alerts_enabled": True,
            "alert_methods": {
                "log": {
                    "enabled": True,
                    "log_level": "WARNING"
                },
                "file": {
                    "enabled": True,
                    "alert_file": r"C:\Users\Administrator\.openclaw\production\logs\alerts.json"
                }
            },
            "alert_templates": {
                "accuracy_critical": "准确率严重告警: {accuracy:.1%} < {threshold}",
                "accuracy_warning": "准确率警告: {accuracy:.1%} < {threshold}",
                "response_time_critical": "响应时间严重告警: {time_ms:.0f}ms > {threshold}ms",
                "response_time_warning": "响应时间警告: {time_ms:.0f}ms > {threshold}ms",
                "system_error": "系统错误: {error}"
            },
            "cooldown_settings": {
                "same_alert_cooldown_minutes": 30,
                "max_alerts_per_hour": 10
            }
        }
        
        with open(alert_config_path, 'w', encoding='utf-8') as f:
            json.dump(alert_config, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] 告警配置文件创建成功: {alert_config_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建告警配置文件失败: {e}")
        return False

def create_monitoring_schedule():
    """创建监控计划"""
    print("\n[INFO] 创建监控计划...")
    
    try:
        schedule_path = r"C:\Users\Administrator\.openclaw\production\config\monitoring_schedule.json"
        
        schedule = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "schedules": [
                {
                    "name": "accuracy_check",
                    "script": r"C:\Users\Administrator\.openclaw\production\scripts\monitor_accuracy.py",
                    "interval_minutes": 5,
                    "enabled": True
                },
                {
                    "name": "performance_check",
                    "script": r"C:\Users\Administrator\.openclaw\production\scripts\monitor_performance.py",
                    "interval_minutes": 10,
                    "enabled": True
                },
                {
                    "name": "system_health",
                    "script": r"C:\Users\Administrator\.openclaw\production\scripts\check_system_health.py",
                    "interval_minutes": 15,
                    "enabled": True
                }
            ],
            "maintenance_window": {
                "enabled": False,
                "start_time": "02:00",
                "end_time": "04:00"
            }
        }
        
        with open(schedule_path, 'w', encoding='utf-8') as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] 监控计划创建成功: {schedule_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建监控计划失败: {e}")
        return False

def create_basic_monitoring_script():
    """创建基础监控脚本"""
    print("\n[INFO] 创建基础监控脚本...")
    
    try:
        scripts_dir = r"C:\Users\Administrator\.openclaw\production\scripts"
        os.makedirs(scripts_dir, exist_ok=True)
        
        # 创建监控脚本
        monitor_script = os.path.join(scripts_dir, "monitor_basic.py")
        script_content = '''#!/usr/bin/env python3
"""
基础监控脚本
检查系统基本状态和算法运行状态
"""

import sys
import os
import json
import time
from datetime import datetime

def check_system_status():
    """检查系统状态"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "system": "OK",
        "algorithm": "OK",
        "data_storage": "OK",
        "monitoring": "OK"
    }
    
    try:
        # 检查算法文件
        algorithm_path = r"C:\\Users\\Administrator\\.openclaw\\production\\v1.8_optimized\\optimized_algorithm_v1_8_optimized.py"
        if not os.path.exists(algorithm_path):
            status["algorithm"] = "ERROR: 算法文件不存在"
        
        # 检查配置文件
        config_path = r"C:\\Users\\Administrator\\.openclaw\\production\\config\\production_config.json"
        if not os.path.exists(config_path):
            status["system"] = "WARNING: 配置文件不存在"
        
        # 检查数据目录
        data_path = r"C:\\Users\\Administrator\\.openclaw\\production\\data"
        if not os.path.exists(data_path):
            status["data_storage"] = "ERROR: 数据目录不存在"
        
        # 检查日志目录
        logs_path = r"C:\\Users\\Administrator\\.openclaw\\production\\logs"
        if not os.path.exists(logs_path):
            status["monitoring"] = "WARNING: 日志目录不存在"
        
    except Exception as e:
        status["system"] = f"ERROR: {str(e)}"
    
    return status

def save_status_report(status):
    """保存状态报告"""
    try:
        logs_dir = r"C:\\Users\\Administrator\\.openclaw\\production\\logs\\status"
        os.makedirs(logs_dir, exist_ok=True)
        
        # 按日期保存
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(logs_dir, f"status_{date_str}.json")
        
        # 读取现有日志或创建新日志
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        else:
            logs = []
        
        logs.append(status)
        
        # 只保留最近100条记录
        if len(logs) > 100:
            logs = logs[-100:]
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] 状态报告已保存: {log_file}")
        
    except Exception as e:
        print(f"[ERROR] 保存状态报告失败: {e}")

def main():
    """主函数"""
    print("=" * 60)
    print("基础监控脚本")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查系统状态
    print("[INFO] 检查系统状态...")
    status = check_system_status()
    
    # 显示状态
    print(f"[STATUS] 系统状态: {status['system']}")
    print(f"[STATUS] 算法状态: {status['algorithm']}")
    print(f"[STATUS] 数据存储: {status['data_storage']}")
    print(f"[STATUS] 监控状态: {status['monitoring']}")
    
    # 保存状态报告
    save_status_report(status)
    
    # 检查是否有错误
    errors = []
    for key, value in status.items():
        if "ERROR" in value:
            errors.append(f"{key}: {value}")
    
    if errors:
        print(f"\n[ERROR] 发现 {len(errors)} 个错误:")
        for error in errors:
            print(f"  - {error}")
        return 1
    elif any("WARNING" in value for value in status.values()):
        print("\n[WARNING] 发现警告")
        return 2
    else:
        print("\n[OK] 所有系统状态正常")
        return 0

if __name__ == "__main__":
    sys.exit(main())
'''
        
        with open(monitor_script, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"[OK] 创建基础监控脚本: {monitor_script}")
        
        # 创建状态检查脚本
        status_script = os.path.join(scripts_dir, "check_deployment_status.py")
        status_content = '''#!/usr/bin/env python3
"""
部署状态检查脚本
检查V1.8_optimized部署状态和回滚准备
"""

import sys
import os
import json
from datetime import datetime

def check_deployment_status():
    """检查部署状态"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "deployment_version": "V1.8_optimized",
        "backup_version": "V1.7_final_backup",
        "checks": {}
    }
    
    # 检查版本文件
    v18_path = r"C:\\Users\\Administrator\\.openclaw\\production\\v1.8_optimized\\optimized_algorithm_v1_8_optimized.py"
    v17_path = r"C:\\Users\\Administrator\\.openclaw\\production\\v1.7_final_backup\\optimized_algorithm_v1_7_final.py"
    
    status["checks"]["v1.8_file"] = os.path.exists(v18_path)
    status["checks"]["v1.7_file"] = os.path.exists(v17_path)
    
    # 检查配置文件
    config_path = r"C:\\Users\\Administrator\\.openclaw\\production\\config\\production_config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            status["checks"]["config_valid"] = True
            status["config_version"] = config.get("version", "UNKNOWN")
        except:
            status["checks"]["config_valid"] = False
    else:
        status["checks"]["config_valid"] = False
    
    # 检查数据目录
    data_dirs = [
        r"C:\\Users\\Administrator\\.openclaw\\production\\data",
        r"C:\\Users\\Administrator\\.openclaw\\production\\data\\chroma",
        r"C:\\Users\\Administrator\\.openclaw\\production\\data\\memory"
    ]
    
    status["checks"]["data_dirs"] = all(os.path.exists(dir) for dir in data_dirs)
    
    # 检查日志目录
    log_dirs = [
        r"C:\\Users\\Administrator\\.openclaw\\production\\logs",
        r"C:\\Users\\Administrator\\.openclaw\\production\\logs\\monitoring"
    ]
    
    status["checks"]["log_dirs"] = all(os.path.exists(dir) for dir in log_dirs)
    
    # 计算总体状态
    all_passed = all(status["checks"].values())
    status["overall_status"] = "OK" if all_passed else "ERROR"
    
    return status

def check_rollback_preparedness():
    """检查回滚准备状态"""
    preparedness = {
        "timestamp": datetime.now().isoformat(),
        "rollback_ready": False,
        "checks": {}
    }
    
    # 检查备份版本
    v17_path = r"C:\\Users\\Administrator\\.openclaw\\production\\v1.7_final_backup\\optimized_algorithm_v1_7_final.py"
    preparedness["checks"]["backup_file_exists"] = os.path.exists(v17_path)
    
    if preparedness["checks"]["backup_file_exists"]:
        # 尝试导入备份版本
        try:
            sys.path.append(r"C:\\Users\\Administrator\\.openclaw\\production\\v1.7_final_backup")
            from optimized_algorithm_v1_7_final import MemoryAnalyzerV1_7_Final
            preparedness["checks"]["backup_importable"] = True
            
            # 测试备份版本功能
            analyzer = MemoryAnalyzerV1_7_Final()
            test_result = analyzer.analyze_memory("测试回滚功能")
            preparedness["checks"]["backup_functional"] = True
            preparedness["test_result"] = test_result["type"]
            
        except ImportError:
            preparedness["checks"]["backup_importable"] = False
            preparedness["checks"]["backup_functional"] = False
        except Exception as e:
            preparedness["checks"]["backup_importable"] = True
            preparedness["checks"]["backup_functional"] = False
            preparedness["error"] = str(e)
    else:
        preparedness["checks"]["backup_importable"] = False
        preparedness["checks"]["backup_functional"] = False
    
    # 检查回滚脚本
    rollback_script = r"C:\\Users\\Administrator\\.openclaw\\production\\scripts\\rollback_to_v1.7.py"
    preparedness["checks"]["rollback_script_exists"] = os.path.exists(rollback_script)
    
    # 计算回滚准备状态
    preparedness["rollback_ready"] = all(preparedness["checks"].values())
    
    return preparedness

def main():
    """主函数"""
    print("=" * 60)
    print("部署状态检查脚本")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查部署状态
    print("\n[INFO] 检查部署状态...")
    deployment_status = check_deployment_status()
    
    print(f"[STATUS] 部署版本: {deployment_status['deployment_version']}")
    print(f"[STATUS] 备份版本: {deployment_status['backup_version']}")
    
    for check_name, check_result in deployment_status["checks"].items():
        status = "[OK]" if check_result else "[ERROR]"
        print(f"{status} {check_name}: {check_result}")
    
    print(f"\n[STATUS] 总体状态: {deployment_status['overall_status']}")
    
    # 检查回滚准备
    print("\n[INFO] 检查回滚准备状态...")
    rollback_status = check_rollback_preparedness()
    
    for check_name, check_result in rollback_status["checks"].items():
        status = "[OK]" if check_result else "[ERROR]"
        print(f"{status} {check_name}: {check_result}")
    
    print(f"\n[STATUS] 回滚准备状态: {'[OK] 就绪' if rollback_status['rollback_ready'] else '[ERROR] 未就绪'}")
    
    # 保存状态报告
    try:
        status_dir = r"C:\Users\Administrator\.openclaw\production\logs\status"
        os.makedirs(status_dir, exist_ok=True)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "deployment_status": deployment_status,
            "rollback_status": rollback_status
        }
        
        report_file = os.path.join(status_dir, f"deployment_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n[INFO] 状态报告已保存: {report_file}")
        
    except Exception as e:
        print(f"[ERROR] 保存状态报告失败: {e}")
    
    # 返回状态码
    if deployment_status["overall_status"] == "ERROR" or not rollback_status["rollback_ready"]:
        print("\n[ERROR] 部署状态检查失败")
        return 1
    else:
        print("\n[OK] 部署状态检查通过")
        return 0

if __name__ == "__main__":
    sys.exit(main())
'''
        
        with open(status_script, 'w', encoding='utf-8') as f:
            f.write(status_content)
        
        print(f"[OK] 创建部署状态检查脚本: {status_script}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建监控脚本失败: {e}")
        return False

def create_rollback_script():
    """创建回滚脚本"""
    print("\n[INFO] 创建回滚脚本...")
    
    try:
        scripts_dir = r"C:\Users\Administrator\.openclaw\production\scripts"
        rollback_script = os.path.join(scripts_dir, "rollback_to_v1.7.py")
        
        rollback_content = '''#!/usr/bin/env python3
"""
回滚脚本
从V1.8_optimized回滚到V1.7_final_backup
"""

import sys
import os
import json
import shutil
from datetime import datetime

def backup_current_version():
    """备份当前版本"""
    print("[INFO] 备份当前V1.8_optimized版本...")
    
    try:
        backup_dir = r"C:\\Users\\Administrator\\.openclaw\\production\\backup\\v1.8_rollback"
        os.makedirs(backup_dir, exist_ok=True)
        
        # 备份算法文件
        v18_source = r"C:\\Users\\Administrator\\.openclaw\\production\\v1.8_optimized"
        v18_backup = os.path.join(backup_dir, "v1.8_optimized")
        
        if os.path.exists(v18_source):
            if os.path.exists(v18_backup):
                shutil.rmtree(v18_backup)
            shutil.copytree(v18_source, v18_backup)
            print(f"[OK] 算法文件备份到: {v18_backup}")
        else:
            print("[WARNING] V1.8_optimized目录不存在，跳过备份")
        
        # 备份配置文件
        config_source = r"C:\\Users\\Administrator\\.openclaw\\production\\config"
        config_backup = os.path.join(backup_dir, "config")
        
        if os.path.exists(config_source):
            if os.path.exists(config_backup):
                shutil.rmtree(config_backup)
            shutil.copytree(config_source, config_backup)
            print(f"[OK] 配置文件备份到: {config_backup}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 备份当前版本失败: {e}")
        return False

def restore_v1_7_version():
    """恢复V1.7_final_backup版本"""
    print("\n[INFO] 恢复V1.7_final_backup版本...")
    
    try:
        # 源目录（备份版本）
        v17_source = r"C:\\Users\\Administrator\\.openclaw\\production\\v1.7_final_backup"
        
        # 目标目录（当前版本位置）
        current_dir = r"C:\\Users\\Administrator\\.openclaw\\production\\current"
        
        # 创建当前版本目录
        os.makedirs(current_dir, exist_ok=True)
        
        # 复制V1.7文件到当前版本目录
        for item in os.listdir(v17_source):
            source_item = os.path.join(v17_source, item)
            dest_item = os.path.join(current_dir, item)
            
            if os.path.isfile(source_item):
                shutil.copy2(source_item, dest_item)
                print(f"[OK] 复制文件: {item}")
            elif os.path.isdir(source_item):
                if os.path.exists(dest_item):
                    shutil.rmtree(dest_item)
                shutil.copytree(source_item, dest_item)
                print(f"[OK] 复制目录: {item}")
        
        # 更新配置文件
        config_path = r"C:\\Users\\Administrator\\.openclaw\\production\\config\\production_config.json"
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config["version"] = "V1.7_final_backup"
            config["rollback_time"] = datetime.now().isoformat()
            config["rollback_reason"] = "从V1.8_optimized回滚"
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            print("[OK] 配置文件已更新为V1.7_final_backup")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 恢复V1.7版本失败: {e}")
        return False

def verify_rollback():
    """验证回滚结果"""
    print("\n[INFO] 验证回滚结果...")
    
    try:
        # 检查当前版本目录
        current_dir = r"C:\\Users\\Administrator\\.openclaw\\production\\current"
        if not os.path.exists(current_dir):
            print("[ERROR] 当前版本目录不存在")
            return False
        
        # 检查V1.7文件是否存在
        v17_file = os.path.join(current_dir, "optimized_algorithm_v1_7_final.py")
        if not os.path.exists(v17_file):
            print("[ERROR] V1.7算法文件不存在")
            return False
        
        # 尝试导入V1.7算法
        sys.path.append(current_dir)
        try:
            from optimized_algorithm_v1_7_final import MemoryAnalyzerV1_7_Final
            print("[OK] V1.7算法可正常导入")
            
            # 测试算法功能
            analyzer = MemoryAnalyzerV1_7_Final()
            test_result = analyzer.analyze_memory("测试回滚后功能")
            print(f"[OK] V1.7算法功能正常，分析结果: {test_result['type']}")
            
            return True
            
        except ImportError as e:
            print(f"[ERROR] 导入V1.7算法失败: {e}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 验证回滚失败: {e}")
        return False

def create_rollback_report():
    """创建回滚报告"""
    print("\n[INFO] 创建回滚报告...")
    
    try:
        report = {
            "rollback_time": datetime.now().isoformat(),
            "from_version": "V1.8_optimized",
            "to_version": "V1.7_final_backup",
            "steps": {
                "backup_current": backup_current_version(),
                "restore_v1_7": restore_v1_7_version(),
                "verify_rollback": verify_rollback()
            },
            "status": "SUCCESS" if all([backup_current_version(), restore_v1_7_version(), verify_rollback()]) else "FAILED"
        }
        
        # 保存报告
        reports_dir = r"C:\\Users\\Administrator\\.openclaw\\production\\logs\\rollback"
        os.makedirs(reports_dir, exist_ok=True)
        
        report_file = os.path.join(reports_dir, f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] 回滚报告已保存: {report_file}")
        
        return report["status"] == "SUCCESS"
        
    except Exception as e:
        print(f"[ERROR] 创建回滚报告失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("回滚脚本 - 从V1.8_optimized回滚到V1.7_final_backup")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    print("\n[WARNING] 即将执行回滚操作！")
    print("此操作将:")
    print("1. 备份当前V1.8_optimized版本")
    print("2. 恢复V1.7_final_backup版本")
    print("3. 更新配置文件")
    print("4. 验证回滚结果")
    
    # 确认执行
    confirm = input("\n确认执行回滚？(输入 'YES' 继续): ")
    if confirm != "YES":
        print("[INFO] 回滚操作已取消")
        return 0
    
    # 执行回滚
    success = create_rollback_report()
    
    if success:
        print("\n" + "=" * 60)
        print("[SUCCESS] 回滚操作完成！")
        print(f"系统已从 V1.8_optimized 回滚到 V1.7_final_backup")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("[ERROR] 回滚操作失败！")
        print("请检查错误日志并手动处理")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
        
        with open(rollback_script, 'w', encoding='utf-8') as f:
            f.write(rollback_content)
        
        print(f"[OK] 创建回滚脚本: {rollback_script}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建回滚脚本失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("监控设置工具")
    print(f"设置时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 执行设置步骤
    steps = [
        ("创建监控配置文件", create_monitoring_config),
        ("创建日志目录结构", create_log_directories),
        ("创建告警配置文件", create_alert_config),
        ("创建监控计划", create_monitoring_schedule),
        ("创建基础监控脚本", create_basic_monitoring_script),
        ("创建回滚脚本", create_rollback_script)
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
        print("\n[监控系统状态]:")
        print("1. [OK] 监控配置文件就绪")
        print("2. [OK] 日志目录结构就绪")
        print("3. [OK] 告警配置就绪")
        print("4. [OK] 监控计划就绪")
        print("5. [OK] 监控脚本就绪")
        print("6. [OK] 回滚脚本就绪")
        return 0
    else:
        print(f"\n[警告] 有{total-passed}个步骤失败，请检查监控设置")
        return 1

if __name__ == "__main__":
    sys.exit(main())
