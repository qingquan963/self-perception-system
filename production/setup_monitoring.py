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

def create_monitoring_scripts():
    """创建监控脚本"""
    print("\n[INFO] 创建监控脚本...")
    
    scripts = [
        {
            "name": "monitor_accuracy.py",
            "content": """#!/usr/bin/env python3
"""
        },
        {
            "name": "monitor_performance.py",
            "content": """#!/usr/bin/env python3
"""
        }
    ]
    
    try:
        scripts_dir = r"C:\Users\Administrator\.openclaw\production\scripts"
        os.makedirs(scripts_dir, exist_ok=True)
        
        # 创建准确率监控脚本
        accuracy_script = os.path.join(scripts_dir, "monitor_accuracy.py")
        accuracy_content = '''#!/usr/bin/env python3
"""
准确率监控脚本
定期检查算法准确率和性能指标
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta

# 添加生产环境路径
sys.path.append(r"C:\\Users\\Administrator\\.openclaw\\production\\v1.8_optimized")

try:
    from optimized_algorithm_v1_8_optimized import MemoryAnalyzerV1_8_Optimized
except ImportError as e:
    print(f"[ERROR] 导入算法失败: {e}")
    sys.exit(1)

def load_monitoring_config():
    """加载监控配置"""
    config_path = r"C:\\Users\\Administrator\\.openclaw\\production\\config\\monitoring_config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 加载监控配置失败: {e}")
        return None

def check_accuracy():
    """检查准确率"""
    print(f"[INFO] 开始准确率检查: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        analyzer = MemoryAnalyzerV1_8_Optimized()
        
        # 测试用例
        test_cases = [
            {"text": "电商套利系统扩展需求分析", "expected_type": "project"},
            {"text": "猫爸要求测试自己封装的DeepSeek技能", "expected_type": "communication"},
            {"text": "第7轮优化结果和行为准则更新", "expected_type": "learning"},
            {"text": "执行Playwright自动化测试", "expected_type": "technical"},
            {"text": "确认项目优先级", "expected_type": "decision"}
        ]
        
        correct = 0
        total = len(test_cases)
        
        for test in test_cases:
            result = analyzer.analyze_memory(test["text"])
            if result["type"] == test["expected_type"]:
                correct += 1
        
        accuracy = correct / total
        
        # 记录结果
        result = {
            "timestamp": datetime.now().isoformat(),
            "accuracy": accuracy,
            "correct": correct,
            "total": total,
            "status": "OK" if accuracy >= 0.95 else "WARNING"
        }
        
        print(f"[RESULT] 准确率: {accuracy:.1%} ({correct}/{total})")
        
        return result
        
    except Exception as e:
        print(f"[ERROR] 准确率检查失败: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "accuracy": 0,
            "error": str(e),
            "status": "ERROR"
        }

def check_response_time():
    """检查响应时间"""
    print(f"[INFO] 开始响应时间检查: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        analyzer = MemoryAnalyzerV1_8_Optimized()
        
        test_text = "今天完成了多个任务：1) 学习了新的算法优化方法 2) 修复了项目中的bug 3) 与团队沟通了进度安排"
        
        # 测量响应时间
        start_time = time.time()
        result = analyzer.analyze_memory(test_text)
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # 转换为毫秒
        
        # 记录结果
        result_data = {
            "timestamp": datetime.now().isoformat(),
            "response_time_ms": response_time,
            "status": "OK" if response_time < 2000 else "WARNING"
        }
        
        print(f"[RESULT] 响应时间: {response_time:.2f}ms")
        
        return result_data
        
    except Exception as e:
        print(f"[ERROR] 响应时间检查失败: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "response_time_ms": 0,
            "error": str(e),
            "status": "ERROR"
        }

def save_monitoring_result(result_type, result_data):
    """保存监控结果"""
    try:
        logs_dir = r"C:\\Users\\Administrator\\.openclaw\\production\\logs\\monitoring"
        os.makedirs(logs_dir, exist_ok=True)
        
        # 按日期保存
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(logs_dir, f"{result_type}_{date_str}.json")
        
        # 读取现有日志或创建新日志
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        else:
            logs = []
        
        logs.append(result_data)
        
        # 只保留最近100条记录
        if len(logs) > 100:
            logs = logs[-100:]
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] 监控结果已保存: {log_file}")
        
    except Exception as e:
        print(f"[ERROR] 保存监控结果失败: {e}")

def check_thresholds(config, accuracy_result, response_time_result):
    """检查阈值并触发告警"""
    if not config:
        return
    
    thresholds = config.get("thresholds", {})
    
    # 检查准确率阈值
    accuracy_threshold = thresholds.get("accuracy", {})
    accuracy = accuracy_result.get("accuracy", 0)
    
    if accuracy < accuracy_threshold.get("critical", 0.90):
        print(f"[ALERT] 准确率严重告警: {accuracy:.1%} < {accuracy_threshold.get('critical')}")
    elif accuracy < accuracy_threshold.get("warning", 0.95):
        print(f"[WARNING] 准确率警告: {accuracy:.1%} < {accuracy_threshold.get('warning')}")
    
    # 检查响应时间阈值
    response_threshold = thresholds.get("response_time", {})
    response_time = response_time_result.get("response_time_ms", 0)
    
    if response_time > response_threshold.get("critical", 5000):
        print(f"[ALERT] 响应时间严重告警: {response_time:.2f}ms > {response_threshold.get('critical')}ms")
    elif response_time > response_threshold.get("warning", 2000):
        print(f"[WARNING] 响应时间警告: {response_time:.2f}ms > {response_threshold.get('warning')}ms")

def main():
    """主函数"""
    print("=" * 60)
    print("准确率监控脚本")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 加载配置
    config = load_monitoring_config()
    if not config:
        print("[ERROR] 无法加载监控配置，使用默认值")
    
    # 执行检查
    accuracy_result = check_accuracy()
    response_time_result = check_response_time()
    
    # 保存结果
    save_monitoring_result("accuracy", accuracy_result)
    save_monitoring_result("response_time", response_time_result)
    
    # 检查阈值
    check_thresholds(config, accuracy_result, response_time_result)
    
    print("\n[INFO] 监控检查完成")
    
    # 返回状态码
    if accuracy_result.get("status") == "ERROR" or response_time_result.get("status") == "ERROR":
        return 1
    elif accuracy_result.get("status") == "WARNING" or response_time_result.get("status") == "WARNING":
        return 2
    else:
        return 0

if __name__ == "__main__":
    sys.exit(main())
'''
        
        with open(accuracy_script, 'w', encoding='utf-8') as f:
            f.write(accuracy_content)
        
        print(f"[OK] 创建准确率监控脚本: {accuracy_script}")
        
        # 创建性能监控脚本
        performance_script = os.path.join(scripts_dir, "monitor_performance.py")
        performance_content = '''#!/usr/bin/env python3
"""
性能监控脚本
监控系统资源使用和性能指标
"""

import sys
import os
import json
import time
import psutil
from datetime import datetime

def get_system_metrics():
    """获取系统指标"""
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage("C:").percent,
        "process_count": len(psutil.pids())
    }
    return metrics

def get_process_metrics(process_name="python"):
    """获取进程指标"""
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "process_name": process_name,
        "process_count": 0,
        "total_memory_mb": 0,
        "total_cpu_percent": 0
    }
    
    try:
        process_count = 0
        total_memory = 0
        total_cpu = 0
        
        for proc in psutil.process_iter(['name', 'memory_percent', 'cpu_percent']):
            try:
                if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                    process_count += 1
                    total_memory += proc.info['memory_percent'] or 0
                    total_cpu += proc.info['cpu_percent'] or 0
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        metrics.update({
            "process_count": process_count,
            "total_memory_mb": total_memory,
            "total_cpu_percent": total_cpu
        })
        
    except Exception as e:
        metrics["error"] = str(e)
    
    return metrics

def save_metrics(metrics_type, metrics_data):
    """保存指标数据"""
    try:
        logs_dir = r"C:\\Users\\Administrator\\.openclaw\\production\\logs\\performance"
        os.makedirs(logs_dir, exist_ok=True)
        
        # 按日期保存
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(logs_dir, f"{metrics_type}_{date_str}.json")
        
        # 读取现有日志或创建新日志
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        else:
            logs = []
        
        logs.append(metrics_data)
        
        # 只保留最近100条记录
        if len(logs) > 100:
            logs = logs[-100:]
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] 指标数据已保存: {log_file}")
        
    except Exception as e:
        print(f"[ERROR] 保存指标数据失败: {e}")

def check_resource_thresholds(system_metrics):
    """检查资源阈值"""
    warnings = []
    
    # CPU阈值检查
    if system_metrics["cpu_percent"] > 80:
        warnings.append(f"CPU使用率高: {system_metrics['cpu_percent']}%")
    
    # 内存阈值检查
    if system_metrics["memory_percent"] > 85:
        warnings.append(f"内存使用率高: {system_metrics['memory_percent']}%")
    
    # 磁盘阈值检查
    if system_metrics["disk_usage"] > 90:
        warnings.append(f"磁盘使用率高: {system_metrics['disk_usage']}%")
    
    return warnings

def main():
    """主函数"""
    print("=" * 60)
    print("性能监控脚本")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # 获取系统指标
        print("[INFO] 获取系统指标...")
        system_metrics = get_system_metrics()
        
        print(f"[INFO] CPU使用率: {system_metrics['cpu_percent']}%")
        print(f"[INFO] 内存使用率: {system_metrics['memory_percent']}%")
        print(f"[INFO] 磁盘使用率: {system_metrics['disk_usage']}%")
        print(f"[INFO] 进程数量: {system_metrics['process_count']}")
        
        # 获取进程指标
        print("\n[INFO] 获取Python进程指标...")
        process_metrics = get_process_metrics("python")
        
        print(f"[INFO] Python进程数量: {process_metrics['process_count']}")
        print(f"[INFO] Python总内存使用: {process_metrics['total_memory_mb']:.1f}MB")
        print(f"[INFO] Python总CPU使用: {process_metrics['total_cpu_percent']:.1f}%")
        
        # 检查资源阈值
        warnings = check_resource_thresholds(system_metrics)
        if warnings:
            print("\n[WARNING] 资源使用警告:")
            for warning in warnings:
                print(f"  - {warning}")
        
        # 保存指标
        save_metrics("system", system_metrics)
        save_metrics("process", process_metrics)
        
        print("\n[INFO] 性能监控完成")
        
        return 0 if not warnings else 1
        
    except Exception as e:
        print(f"[ERROR] 性能监控失败: {e}")
        return 2

if __name__ == "__main__":
    sys.exit(main())
'''
        
        with open(performance_script, 'w', encoding='utf-8') as f:
            f.write(performance_content)
        
        print(f"[OK] 创建性能监控脚本: {performance_script}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建监控脚本失败: {e}")
        return False

def create_log_directories():
    """创建日志目录结构"""
    print("\n[INFO] 创建日志目录结构...")
    
    try:
        log_dirs = [
            r"C:\Users\Administrator\.openclaw\production\logs\monitoring",
            r"C:\Users\Administrator\.openclaw\production\logs\performance",
            r"C:\Users\Administrator\.openclaw\production\logs\errors",
            r"C:\Users