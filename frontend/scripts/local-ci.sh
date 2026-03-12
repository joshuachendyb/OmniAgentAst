#!/bin/bash
# scripts/local-ci.sh - 本地CI/CD自动化脚本
# 作者：老杨（AI助手）
# 创建时间：2026-02-27 16:56:03
# 版本：v1.0
# 适用项目：OmniAgentAs-desk 前端项目

set -e  # 出错立即停止执行
set -o pipefail  # 管道命令失败时也停止

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "未找到命令 $1，请先安装"
        exit 1
    fi
}

# 检查Node.js和npm版本
check_node_version() {
    log_info "检查Node.js和npm版本..."
    
    local node_version=$(node -v | cut -d'v' -f2)
    local npm_version=$(npm -v)
    
    log_info "Node.js: v$node_version"
    log_info "npm: v$npm_version"
    
    # 检查Node.js版本是否满足要求
    IFS=. read -r major minor patch <<< "$node_version"
    if [ "$major" -lt 18 ]; then
        log_warning "Node.js版本建议 >= 18，当前版本为 $node_version"
    fi
}

# 安装依赖
install_dependencies() {
    log_info "检查依赖..."
    
    if [ ! -d "node_modules" ]; then
        log_info "📦 安装项目依赖..."
        npm install
        log_success "依赖安装成功"
    else
        log_info "依赖已存在，跳过安装"
    fi
}

# 代码质量检查
run_lint() {
    log_info "🔍 运行ESLint代码质量检查..."
    npm run lint
    log_success "代码质量检查通过"
}

# 单元测试
run_tests() {
    log_info "🧪 运行单元测试..."
    npm run test
    log_success "所有单元测试通过"
}

# 生成覆盖率报告
run_coverage() {
    log_info "📊 生成测试覆盖率报告..."
    npm run test:coverage
    log_success "覆盖率报告生成成功"
    log_info "报告位置: coverage/index.html"
}

# 构建项目
run_build() {
    log_info "🔨 执行生产环境构建..."
    npm run build
    log_success "项目构建成功"
    log_info "构建产物: dist/ 目录"
}

# 显示最终结果
show_result() {
    log_success "=== 本地CI/CD流程执行完成 ==="
    echo ""
    log_info "✅ 所有检查项通过"
    log_info "✅ 项目代码质量良好"
    log_info "✅ 可以安全提交和部署"
}

# 主流程
main() {
    local start_time=$(date +%s)
    
    echo "============================================"
    echo -e "${BLUE}OmniAgentAs-desk 前端项目本地CI/CD自动化${NC}"
    echo "============================================"
    echo "执行时间: $(date +"%Y-%m-%d %H:%M:%S")"
    echo ""
    
    # 检查必要命令
    check_command node
    check_command npm
    
    # 检查Node.js版本
    check_node_version
    
    echo ""
    log_info "开始执行本地CI/CD流程..."
    
    # 执行各个阶段
    install_dependencies
    run_lint
    run_tests
    run_build
    
    # 可选：是否生成覆盖率报告
    read -p "是否需要生成测试覆盖率报告? (y/N): " generate_coverage
    if [[ "$generate_coverage" == "y" || "$generate_coverage" == "Y" ]]; then
        run_coverage
    fi
    
    echo ""
    
    # 计算执行时间
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "执行时间: ${duration}秒"
    
    show_result
}

# 错误处理
trap 'log_error "CI流程中断，错误码: $?"; exit 1' INT TERM

# 执行主流程
main "$@"