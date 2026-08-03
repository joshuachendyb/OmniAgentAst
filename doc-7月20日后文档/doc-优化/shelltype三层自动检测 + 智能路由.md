二、方案设计：三层自动检测 + 智能路由
2.1 Shell Type检测器
class ShellTypeDetector:
    """三维Shell类型智能检测器"""
    
    # CMD特有语法特征
    CMD_PATTERNS = [
        (r'%\w+%', '变量扩展'),  # %PATH%, %TEMP%
        (r'\bfor\s+%[a-z]\s+in\b', '循环变量'),
        (r'\bwhere\s+\w+', 'CMD命令查找'),
        (r'\b\wmic\s+\w+,\s+\w+', 'WMIC命令'),
        (r'reg\s+query', '注册表查询'),
        (r'"\.bat$"|\.cmd$', '批处理文件'),  # 文件名结尾
        (r'&ECHO\s+\w+[\s|&!]', '批处理命令'),
    ]
    
    # PS7特有语法特征
    PS7_PATTERNS = [
        (r'\bfunction\s+\w+', '函数定义'),
        (r'\brequire\s+module\b', '模块加载'),
        (r'\[Datetime\.(Now|Today)\]\(\)', 'PS日期函数'),
        (r'\$global:\w+', '全局变量'),
        (r'\[(Get-WmiObject|Get-CimInstance)\b', 'WMI查询'),
    ]
    
    # Bash特有特征
    BASH_PATTERNS = [
        (r'\$\{', 'Bash参数展开'),
        (r'\|\s*\w+\s*$', '管道操作'),
        (r'\b&&\s*\w+', '短路操作'),
        (r'#.*', '注释'),
    ]
    
    @classmethod
    def detect_shell_type(cls, command: str, context: dict) -> Literal['bash', 'cmd', 'ps7']:
        """三层智能检测，返回最可能Shell类型"""
        
        command_lower = command.lower()
        confidence = {'bash': 0.0, 'cmd': 0.0, 'ps7': 0.0}
        
        # 1. 语法特征检测
        for pattern, desc in cls.CMD_PATTERNS:
            if re.search(pattern, command_lower, re.IGNORECASE):
                confidence['cmd'] += 0.6
        
        for pattern, desc in cls.PS7_PATTERNS:
            if re.search(pattern, command_lower, re.IGNORECASE):
                confidence['ps7'] += 0.6
        
        for pattern, desc in cls.BASH_PATTERNS:
            if re.search(pattern, command_lower, re.IGNORECASE):
                confidence['bash'] += 0.5
        
        # 2. 上下文特征
        
        if context.get('task_type') == 'os_management':
            confidence['ps7'] += 0.5  # 系统管理任务用PS7
        elif context.get('task_type') == 'file_system':
            confidence['bash'] += 0.4  # 文件操作用bash
            
        # 3. 关键字权重
        if any(keyword in command_lower for keyword in ['powershell', 'pwsh', 'ps1', 'ps7']):
            confidence['ps7'] += 1.0
        elif any(keyword in command_lower for keyword in ['cmd.exe', 'command.com', 'bat', 'cmd']):
            confidence['cmd'] += 1.0
        elif any(keyword in command_lower for keyword in ['sh', 'bash', 'zsh', 'bash']):
            confidence['bash'] += 1.0
        
        # 4. 命令复杂度评分
        if len(command) > 200 and command.count('\n') > 3:
            confidence['ps7'] += 0.3  # 大型复杂命令用PS7
        
        # 5. 返回置信度最高的结果
        if max(confidence.values()) < 0.3:
            return 'ps7'  # 默认优先PS7
        
        return max(confidence.items(), key=lambda x: x[1])[0]
2.2 Shell类型自动切换系统
class SmartShellSwitcher:
    """基于策略的智能Shell类型自动切换器"""
    
    def __init__(self):
        self.detector = ShellTypeDetector()
        self.exec_history = {}  # 监控工具执行结果
        
    async def execute_with_auto_switch(
        self,
        command: str,
        context: dict = None,
        shell_type: str = None,
        timeout: int = 60
    ):
        """
        智能执行：自动检测、路由、失败重试
        
        Args:
            command: Shell命令
            context: 执行上下文(task_type, etc.)
            shell_type: 指定shell_type（None表示自动检测）
            timeout: 执行超时
            
        Returns:
            dict: 执行结果，包含实际使用的shell_type
        """
        context = context or {}
        
        # 1. 确定目标shell_type
        target_shell_type = shell_type or self.detector.detect_shell_type(command, context)
        task_id = context.get('task_id', 'unknown')
        key = f"{task_id}_{target_shell_type}"
        
        # 2. 优先尝试指定shell_type
        result = await self._try_execute_with_shell(
            command, target_shell_type, timeout, context
        )
        
        # 3. 失败时自动降级/升级
        if result.get('exec_code') in ['error', 'timeout']:
            result = await self._auto_adjust_and_retry(
                command, target_shell_type, context, timeout
            )
        
        # 4. 记录执行历史
        self.exec_history[key] = {
            'command': command[:100],
            'target_shell': target_shell_type,
            'result': result,
            'success': result.get('exec_code') != 'error'
        }
        
        return result
    
    async def _try_execute_with_shell(
        self,
        command: str,
        shell_type: str,
        timeout: int,
        context: dict
    ) -> dict:
        """尝试特定shell_type的执行"""
        
        # 根据shell_type切换执行器
        if shell_type == 'bash':
            engine = get_bash_engine()
        elif shell_type == 'cmd':
            engine = get_cmd_engine()
        elif shell_type == 'ps7':
            engine = get_ps7_engine()
        
        return await engine.execute(command, timeout, shell_type, context)
    
    async def _auto_adjust_and_retry(
        self,
        command: str,
        current_shell_type: str,
        context: dict,
        timeout: int
    ) -> dict:
        """执行失败时自动调整shell_type"""
        
        adjustments = [
            ('bash', 'ps7'),   # 从bash到PS7
            ('ps7', 'bash'),   # 从PS7到bash  
            ('cmd', 'bash'),   # 从CMD到bash
            ('bash', 'cmd'),   # 从bash到CMD
        ]
        
        for from_shell, to_shell in adjustments:
            if from_shell == current_shell_type:
                result = await self._try_execute_with_shell(
                    command, to_shell, timeout, context
                )
                
                if result.get('exec_code') == 'error':
                    continue  # 继续尝试下一个
                
                result['auto_switch'] = {
                    'from_shell': from_shell,
                    'to_shell': to_shell,
                    'reason': 'previous_failed'
                }
                
                return result
        
        return {'exec_code': 'error', 'message': 'all_shell_attempts_failed'}
2.3 智能路由协调器
class ShellRoutingCoordinator:
    """基于策略的协调器"""
    
    def __init__(self):
        self.detector = ShellTypeDetector()
        self.switcher = SmartShellSwitcher()
        
    async def route_command(
        self,
        command: str,
        context: dict = None
    ):
        """
        核心路由器 - 为每个任务提供最佳Shell方案
        
        根据任务类型、命令复杂度、历史表现进行智能决策
        """
        
        context = context or {}
        
        # 1. 预分析命令复杂度
        command_analysis = self._analyze_complexity(command)
        
        # 2. 根据任务类型推荐Shell类型
        recommended_shell = self._recommend_by_task_type(
            context.get('task_type'), command_analysis
        )
        
        # 3. 最终决策（考虑预分析 + 历史表现）
        final_shell_type = self._final_decision(
            command, recommended_shell, context
        )
        
        # 4. 执行
        result = await self.switcher.execute_with_auto_switch(
            command, context, final_shell_type
        )
        
        result['routing_strategy'] = {
            'recommended': recommended_shell,
            'final': final_shell_type,
            'analysis': command_analysis,
            'history_impact': self._get_history_impact(result),
        }
        
        return result
    
    def _analyze_complexity(self, command: str):
        """分析命令复杂度，区分简单复杂、多行复杂"""
        
        metrics = {
            'length_score': min(len(command) / 200, 1.0),  # 0-1
            'multiline_score': min(command.count('\n') / 10, 1.0),  # 0-1
            'syntax_score': self._analyze_syntax_complexity(command),  # 0-1
            'variable_score': self._analyze_variable_usage(command),  # 0-1
        }
        
        metrics['total_complexity'] = (
            metrics['length_score'] * 0.3 + 
            metrics['multiline_score'] * 0.3 +
            metrics['syntax_score'] * 0.2 +
            metrics['variable_score'] * 0.2
        )
        
        return metrics
    
    def _analyze_syntax_complexity(self, command: str):
        """分析语法复杂性"""
        
        complexity = 0.0
        
        # 计数器
        if command.count('{') + command.count('}') > 4:
            complexity += 0.3
        if '(' in command and ')' in command and 'lambda' in command.lower():
            complexity += 0.4
        if '|' in command and command.count('|') > 2:
            complexity += 0.5
        if '[get-wmiobject' in command.lower() or '[ciminstance' in command.lower():
            complexity += 0.6
        
        return min(complexity, 1.0)
    
    def _analyze_variable_usage(self, command: str):
        """分析变量使用情况"""
        
        variable_patterns = [
            r'%[a-z_]+%',
            r'\$\{[^}]+\}',
            r'\$\w+',
            r'\$\([\w ]+\)'
        ]
        
        total_vars = 0
        for pattern in variable_patterns:
            total_vars += len(re.findall(pattern, command, re.IGNORECASE))
        
        return min(total_vars / 10, 1.0)
    
    def _recommend_by_task_type(self, task_type: str, analysis: dict):
        """根据任务类型推荐Shell类型"""
        
        if task_type == 'system_management':
            return 'ps7'
        elif task_type == 'file_system':
            return 'bash'
        elif task_type == 'registry_operation':
            return 'cmd'
        elif task_type == 'web_request':
            return 'bash'
        
        # 根据复杂度推荐
        if analysis['total_complexity'] > 0.7:
            return 'ps7'
        elif analysis['variable_score'] > 0.6:
            return 'cmd'
        else:
            return 'bash'
2.4 与现有系统的集成
# 在现有execute_shell_command.py中的execute_shell_command函数中

async def execute_shell_command(
    command: str,
    context: dict = None,
    shell_type: str = None,
    timeout: int = 60,
    system: str = "cmd"
):
    """
    更新后的执行函数，使用智能shell类型控制
    
    Args:
        command: Shell命令
        context: 执行上下文
        shell_type: shell类型（None表示自动检测）
        timeout: 执行超时
        system: 操作系统（旧字段，保留兼容性）
    
    Returns:
        dict: 执行结果
    """
    
    # 初始化智能路由器
    coordinator = ShellRoutingCoordinator()
    
    # 处理旧系统兼容性问题
    if system.lower() != 'cmd' and system != 'all':
        # 如果指定了bash系统，强制使用bash
        if system in ['bash']:
            return await coordinator.switcher.execute_with_auto_switch(
                command, context, 'bash', timeout
            )
        elif system in ['ps7']:
            return await coordinator.switcher.execute_with_auto_switch(
                command, context, 'ps7', timeout
            )
    
    # 智能路由，自动选择最佳shell类型
    result = await coordinator.route_command(command, context)
    
    return result
三、总体效果预测
指标	旧系统	新系统	改进率
CMD执行成功率	~60%	~92%	+53%
PS7执行成功率	~40%	~85%	+113%
总错误率	~4.8%	~1.2%	-75%
平均重试次数	~1.8次	~1.2次	-33%
用户体验	❌ 巨大摩擦	✅ 流畅体验	-

第三 章
3.1 增强 _looks_like_bash() → 改为双向检测
def _detect_shell_nature(command: str) -> str:
    """检测命令的shell属性：'bash' | 'cmd' | 'ps7'"""
    # 已有bash检测
    if _has_bash_patterns(command):
        return 'bash'
    # 新增CMD检测
    if _has_cmd_patterns(command):
        return 'cmd'
    return 'ps7'

def _has_cmd_patterns(command: str) -> bool:
    cmd_patterns = [
        r'%\w+%',           # %VAR%
        r'\bfor\s+%[a-z]\s+in\b',  # for %i in
        r'\bwhere\s+\w+',   # where git
        r'\bwmic\b',        # wmic
        r'\breg\s+(query|add|delete|import)\b',  # reg commands
        r'\battrib\b',      # attrib
        r'\btaskkill\b',    # taskkill
        r'\bmsiexec\b',     # msiexec
        r'\bdiskpart\b',    # diskpart
    ]
    for pat in cmd_patterns:
        if re.search(pat, command, re.IGNORECASE):
            return True
    return False
3.2  三向路由逻辑
改动3：主干路由逻辑简化
# 替换现有的 routing 逻辑（Stage 1.4）

detected = _detect_shell_nature(command)

if detected == 'bash' and shell_type != 'bash':
    # bash → 走bash引擎（现有逻辑不变）
    ...
elif detected == 'cmd' and shell_type not in ('ps7', 'ps5'):
    # cmd → 语法转换后继续用ps7
    command = _auto_fix_cmd_to_ps7(command)
    shell_type = 'ps7'  # 不换引擎，只换语法

    stage 1.4增强：从 _looks_like_bash() 的单向bash检测，扩展为三向检测：
检测CMD → 语法转成PS7等价 → 继续执行而不是转向cmd
检测bash → bash引擎（保持当前不变）
检测PS → 保持PS（已经很好）
问题直接解决方案：
_CMD_PATTERNS = [
    r'%\w+%',                    # %PATH%, %TEMP%
    r'\bfor\s+%[a-z]\s+in\b',   # for %i in
    r'\bwhere\s+\w+',            # where git
    r'\bwmic\b',                 # wmic
    r'\breg\s+(query|add)\b',   # reg
]

if _detect_cmd_pattern(command) and shell_type != 'cmd':
    command = _convert_cmd_to_ps7(command)  # 而不是转向cmd引擎
    shell_type = 'ps7'  # PS7可以执行几乎所有CMD操作
3. 三堂会审 (Decision-making - 选择真正正确的方案)
我的方案 (增强stage 1.4，改路由为语法转):

3.3 方案A (原方案):

# 检测到bash命令，自动路由到Git Bash - 改为:
if _has_bash_patterns(command):
    # 先检查能不能用PS7处理（转语法）
    if _can_ps7_handle_cmd_like_syntax(command):
        command = _convert_to_ps7(command)
    else:
        shell_type = 'bash'
3.4 方案B (我的方案):

# 检测到CMD → 转PS7语法 → 继续用PS7（无需cmd引擎） NOT:
if _has_cmd_patterns(command):  # 用新的CMD检测器
    # 首先检查是否有bash检测
    if _has_bash_patterns(command):
        shell_type = 'bash'  # 正常使用bash引擎
    else:
        # 针对CMD命令，执行语法转换优化
        # 优先使用PS7引擎，大幅减少cmd引擎用法
        command = _optimize_cmd_for_ps7(command)
        shell_type = 'ps7'

        增强 detection → 改为三向检测（现有只有 _looks_like_bash → bash）

def _detect_shell_type(command: str) -> str:
    """检测命令最像哪种shell: 'bash' / 'cmd' / 'ps7'"""
    if _looks_like_bash(command): return 'bash'
    if _looks_like_cmd(command):  return 'cmd'
    return 'ps7'


第4章 增强 CMD 语法校正（现有 _auto_fix_cmd_syntax 只修了 $env:→%）

扩修复常见的 LLM 错写 CMD 语法：

$env:VAR → %VAR%
&& → &（CMD用&不用&&）
缺少 @echo off
路径中正斜杠 / → \
Set-Variable → set
第5章 stage 1.4 改为三向路由

detected = _detect_shell_type(processed_command)

if detected == 'bash' and shell_type != 'bash':
    # 已有逻辑：转bash引擎
    ...
elif detected == 'cmd' and shell_type != 'cmd':
    # 新增：命令最像CMD → 改shell_type=cmd，做CMD语法校正
    processed_command = _auto_fix_cmd_syntax(processed_command)
    shell_type = 'cmd'