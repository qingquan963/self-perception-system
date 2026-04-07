#!/usr/bin/env python3
"""
生产环境测试脚本
用于验证V1.8_optimized部署的正确性
"""

import sys
import os
import json
import time
from datetime import datetime

# 添加生产环境路径
sys.path.append(r"C:\Users\Administrator\.openclaw\production\v1.8_optimized")

try:
    from optimized_algorithm_v1_8_optimized import MemoryAnalyzerV1_8_Optimized
    print("✅ 成功导入V1.8_optimized算法")
except ImportError as e:
    print(f"❌ 导入V1.8_optimized算法失败: {e}")
    sys.exit(1)

def test_basic_functionality():
    """测试基础功能"""
    print("\n=== 基础功能测试 ===")
    
    try:
        # 创建分析器实例
        analyzer = MemoryAnalyzerV1_8_Optimized()
        print("✅ 成功创建MemoryAnalyzerV1_8_Optimized实例")
        
        # 测试关键词库
        keywords = analyzer.keywords
        if keywords and isinstance(keywords, dict):
            print(f"✅ 关键词库加载成功，包含{len(keywords)}个类别")
        else:
            print("❌ 关键词库加载失败")
            return False
        
        # 测试类型权重
        type_weights = analyzer.type_weights
        expected_types = ["learning", "project", "technical", "decision", "communication"]
        if all(t in type_weights for t in expected_types):
            print("✅ 类型权重配置正确")
        else:
            print("❌ 类型权重配置不完整")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ 基础功能测试失败: {e}")
        return False

def test_accuracy():
    """测试准确率"""
    print("\n=== 准确率测试 ===")
    
    try:
        analyzer = MemoryAnalyzerV1_8_Optimized()
        
        # 测试样本
        test_cases = [
            {
                "text": "今天学习了Python的机器学习算法，包括决策树和随机森林",
                "expected_type": "learning"
            },
            {
                "text": "完成了项目A的API接口开发，测试通过",
                "expected_type": "project"
            },
            {
                "text": "需要确认一下明天的会议时间和地点",
                "expected_type": "communication"
            }
        ]
        
        correct = 0
        total = len(test_cases)
        
        for i, test in enumerate(test_cases, 1):
            result = analyzer.analyze_memory(test["text"])
            predicted_type = result["type"]
            
            if predicted_type == test["expected_type"]:
                print(f"✅ 测试用例{i}: 类型识别正确 ({predicted_type})")
                correct += 1
            else:
                print(f"❌ 测试用例{i}: 类型识别错误 (预测: {predicted_type}, 期望: {test['expected_type']})")
        
        accuracy = correct / total
        print(f"📊 准确率: {accuracy:.1%} ({correct}/{total})")
        
        return accuracy >= 0.95
        
    except Exception as e:
        print(f"❌ 准确率测试失败: {e}")
        return False

def test_performance():
    """测试性能"""
    print("\n=== 性能测试 ===")
    
    try:
        analyzer = MemoryAnalyzerV1_8_Optimized()
        
        # 测试文本
        test_text = "今天完成了多个任务：1) 学习了新的算法优化方法 2) 修复了项目中的bug 3) 与团队沟通了进度安排"
        
        # 测量响应时间
        start_time = time.time()
        result = analyzer.analyze_memory(test_text)
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # 转换为毫秒
        
        print(f"📊 响应时间: {response_time:.2f}ms")
        print(f"📊 分析结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        return response_time < 2000  # 2秒内
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        return False

def test_rollback_capability():
    """测试回滚能力"""
    print("\n=== 回滚能力测试 ===")
    
    try:
        # 检查备份版本是否存在
        backup_path = r"C:\Users\Administrator\.openclaw\production\v1.7_final_backup\optimized_algorithm_v1_7_final.py"
        
        if os.path.exists(backup_path):
            print("✅ 备份版本文件存在")
            
            # 尝试导入备份版本
            sys.path.append(r"C:\Users\Administrator\.openclaw\production\v1.7_final_backup")
            try:
                from optimized_algorithm_v1_7_final import MemoryAnalyzerV1_7_Final
                print("✅ 备份版本可正常导入")
                
                # 测试备份版本功能
                backup_analyzer = MemoryAnalyzerV1_7_Final()
                test_result = backup_analyzer.analyze_memory("测试回滚功能")
                print(f"✅ 备份版本功能正常，分析结果: {test_result['type']}")
                
                return True
                
            except ImportError as e:
                print(f"❌ 备份版本导入失败: {e}")
                return False
        else:
            print(f"❌ 备份版本文件不存在: {backup_path}")
            return False
            
    except Exception as e:
        print(f"❌ 回滚能力测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("生产环境部署测试 - V1.8_optimized")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    tests = [
        ("基础功能", test_basic_functionality),
        ("准确率", test_accuracy),
        ("性能", test_performance),
        ("回滚能力", test_rollback_capability)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 开始测试: {test_name}")
        success = test_func()
        results.append((test_name, success))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\n📊 通过率: {passed}/{total} ({passed/total:.1%})")
    
    if passed == total:
        print("\n🎉 所有测试通过！生产环境部署成功！")
        return 0
    else:
        print(f"\n⚠️  有{total-passed}个测试失败，请检查部署")
        return 1

if __name__ == "__main__":
    sys.exit(main())