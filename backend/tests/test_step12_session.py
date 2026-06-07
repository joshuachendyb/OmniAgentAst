"""
测试步骤12：删除session.py中的重复DDL
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_session_py_no_create_table():
    """测试session.py中没有CREATE TABLE语句"""
    try:
        with open("app/services/agent/session.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否没有CREATE TABLE语句（除了可能的注释）
        lines = content.split('\n')
        for line in lines:
            # 跳过注释行
            if line.strip().startswith('#'):
                continue
            # 检查是否有CREATE TABLE
            if 'CREATE TABLE' in line.upper() or 'CREATE TABLE IF NOT EXISTS' in line.upper():
                print(f"❌ session.py中仍有CREATE TABLE语句: {line.strip()}")
                return False
        
        print("✅ test_session_py_no_create_table passed")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_session_py_has_init_db():
    """测试session.py有_init_db方法（但不再建表）"""
    try:
        with open("app/services/agent/session.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否有_init_db方法
        assert '_init_db(' in content, "session.py应该有_init_db方法"
        assert '建表已由' in content or '不再重复' in content, "应该有注释说明建表已移至file_safety.py"
        
        print("✅ test_session_py_has_init_db passed")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_file_safety_py_has_create_table():
    """测试file_safety.py中有CREATE TABLE语句"""
    try:
        # 检查file_safety.py是否有建表语句
        import glob
        files = glob.glob("app/services/**/file_safety.py", recursive=True)
        if not files:
            print("⚠️ file_safety.py not found, skip")
            return True
        
        file_safety = files[0]
        with open(file_safety, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否有CREATE TABLE语句
        assert 'CREATE TABLE' in content.upper(), f"{file_safety} 应该有CREATE TABLE语句"
        
        print("✅ test_file_safety_py_has_create_table passed")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_operation_record_field_name():
    """测试OperationRecord模型使用task_id而非session_id"""
    try:
        with open("app/models/file_operations/__init__.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查OperationRecord是否使用task_id
        # 找到OperationRecord类定义
        lines = content.split('\n')
        in_operation_record = False
        found_task_id = False
        
        for line in lines:
            if 'class OperationRecord' in line:
                in_operation_record = True
            if in_operation_record and 'session_id' in line and 'task_id' not in line:
                print(f"❌ OperationRecord仍有session_id字段: {line.strip()}")
                return False
            if in_operation_record and 'task_id' in line:
                found_task_id = True
            if in_operation_record and line.strip() == '':
                break
        
        assert found_task_id, "OperationRecord应该包含task_id字段"
        
        print("✅ test_operation_record_field_name passed")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_session_record_field_name():
    """测试SessionRecord模型使用task_id而非session_id"""
    try:
        with open("app/models/file_operations/__init__.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查SessionRecord是否使用task_id
        lines = content.split('\n')
        in_session_record = False
        found_task_id = False
        
        for line in lines:
            if 'class SessionRecord' in line:
                in_session_record = True
            if in_session_record and 'session_id' in line and 'task_id' not in line:
                print(f"❌ SessionRecord仍有session_id字段: {line.strip()}")
                return False
            if in_session_record and 'task_id' in line:
                found_task_id = True
            if in_session_record and line.strip() == '':
                break
        
        assert found_task_id, "SessionRecord应该包含task_id字段"
        
        print("✅ test_session_record_field_name passed")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


if __name__ == "__main__":
    r1 = test_session_py_no_create_table()
    r2 = test_session_py_has_init_db()
    r3 = test_file_safety_py_has_create_table()
    r4 = test_operation_record_field_name()
    r5 = test_session_record_field_name()
    
    if all([r1, r2, r3, r4, r5]):
        print("\n✅ 所有步骤12测试通过!")
    else:
        print("\n❌ 有测试失败")
